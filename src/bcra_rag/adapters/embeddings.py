from __future__ import annotations

from typing import Any, cast

import structlog
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from bcra_rag.settings import Settings

log = structlog.get_logger(__name__)

_BACKENDS = frozenset({"auto", "openai", "onnx", "deterministic"})


class DeterministicEmbeddingFunction(EmbeddingFunction[Documents]):
    """Local embeddings so tests never call a paid API or download ONNX."""

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        vectors: list[list[float]] = []
        for text in input:
            vec = [0.0] * self._dim
            data = text.encode("utf-8")
            for i, byte in enumerate(data):
                vec[i % self._dim] += byte / 255.0
            vectors.append(vec)
        return cast(Embeddings, vectors)

    @staticmethod
    def name() -> str:
        return "deterministic"

    def get_config(self) -> dict[str, Any]:
        return {"dim": self._dim}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> DeterministicEmbeddingFunction:
        return DeterministicEmbeddingFunction(dim=int(config.get("dim", 8)))


class OpenAICompatibleEmbeddingFunction(EmbeddingFunction[Documents]):
    """OpenAI-compatible embeddings, batched so local llama.cpp servers do not hang."""

    def __init__(
        self,
        *,
        api_key: str,
        api_base: str,
        model_name: str,
        batch_size: int = 8,
        timeout_s: float = 120.0,
        max_chars: int = 2048,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._model_name = model_name
        self._batch_size = max(1, batch_size)
        self._timeout_s = timeout_s
        self._max_chars = max_chars
        self._client = client

    def _client_or_create(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._api_base,
                timeout=self._timeout_s,
                max_retries=2,
            )
        return self._client

    def __call__(self, input: Documents) -> Embeddings:
        texts = [self._clip(str(text)) for text in input]
        vectors: list[list[float]] = []
        total = len(texts)
        for start in range(0, total, self._batch_size):
            batch = texts[start : start + self._batch_size]
            log.info(
                "embedding_batch",
                done=start,
                batch=len(batch),
                total=total,
                model=self._model_name,
            )
            vectors.extend(self._embed_batch(batch))
        return cast(Embeddings, vectors)

    def _clip(self, text: str) -> str:
        if len(text) <= self._max_chars:
            return text
        log.warning(
            "embedding_truncated",
            chars=len(text),
            max_chars=self._max_chars,
            model=self._model_name,
        )
        return text[: self._max_chars]

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        try:
            return self._create(batch)
        except Exception:
            if len(batch) == 1:
                text = batch[0]
                if len(text) <= 256:
                    raise
                clipped = text[: max(len(text) // 2, 256)]
                log.warning(
                    "embedding_truncated_retry",
                    chars=len(clipped),
                    model=self._model_name,
                )
                return self._embed_batch([clipped])
            mid = max(1, len(batch) // 2)
            return self._embed_batch(batch[:mid]) + self._embed_batch(batch[mid:])

    def _create(self, batch: list[str]) -> list[list[float]]:
        response = self._client_or_create().embeddings.create(
            model=self._model_name,
            input=batch,
        )
        rows = list(response.data)
        by_index = {int(item.index): item.embedding for item in rows}
        if set(by_index) == set(range(len(batch))):
            return [list(by_index[i]) for i in range(len(batch))]
        return [list(item.embedding) for item in rows]

    @staticmethod
    def name() -> str:
        return "openai_compatible"

    def get_config(self) -> dict[str, Any]:
        return {
            "model_name": self._model_name,
            "api_base": self._api_base,
            "batch_size": self._batch_size,
            "timeout_s": self._timeout_s,
            "max_chars": self._max_chars,
        }

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> OpenAICompatibleEmbeddingFunction:
        return OpenAICompatibleEmbeddingFunction(
            api_key="",
            api_base=str(config.get("api_base") or "https://api.openai.com/v1"),
            model_name=str(config.get("model_name") or "text-embedding-3-small"),
            batch_size=int(config.get("batch_size") or 8),
            timeout_s=float(config.get("timeout_s") or 120.0),
            max_chars=int(config.get("max_chars") or 2048),
        )


def _onnx_embedding_function() -> Any:
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    return ONNXMiniLM_L6_V2()


def resolve_embedding_function(
    settings: Settings,
    override: Any | None = None,
) -> Any:
    if override is not None:
        return override
    backend = (settings.embedding_backend or "auto").strip().lower()
    if backend not in _BACKENDS:
        backend = "auto"
    if backend == "onnx":
        return _onnx_embedding_function()
    if backend == "deterministic":
        return DeterministicEmbeddingFunction()
    use_openai = backend == "openai" or (
        backend == "auto" and bool(settings.embedding_api_key)
    )
    if use_openai:
        if not settings.embedding_api_key:
            raise ValueError(
                "EMBEDDING_API_KEY is required when EMBEDDING_BACKEND=openai"
            )
        return OpenAICompatibleEmbeddingFunction(
            api_key=settings.embedding_api_key,
            api_base=settings.embedding_base_url,
            model_name=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
            timeout_s=settings.embedding_timeout_s,
            max_chars=settings.embedding_max_chars,
        )
    return DeterministicEmbeddingFunction()
