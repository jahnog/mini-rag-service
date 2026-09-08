from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from bcra_rag.domain.guardrails.pipeline import NoOpTracer
from bcra_rag.domain.guardrails.types import Tracer
from bcra_rag.domain.models import Chunk
from bcra_rag.settings import Settings

_CONTENT_LIMIT = 2000


def build_tracer(settings: Settings, *, api_key: str = "") -> Tracer:
    endpoint = _collector_endpoint()
    if not endpoint:
        return NoOpTracer()
    try:
        return _phoenix_tracer(settings, endpoint, api_key=api_key)
    except Exception:
        return NoOpTracer()


def _collector_endpoint() -> str:
    import os

    return (os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") or "").strip()


def _resolved_api_key(api_key: str = "") -> str:
    import os

    explicit = (api_key or "").strip()
    if explicit:
        return explicit
    return (os.environ.get("PHOENIX_API_KEY") or "").strip()


def phoenix_register_kwargs(endpoint: str, *, api_key: str = "") -> dict[str, str | bool]:
    kwargs: dict[str, str | bool] = {
        "project_name": _project_name(),
        "endpoint": endpoint,
        "protocol": "http/protobuf",
        "batch": True,
    }
    key = _resolved_api_key(api_key)
    if key:
        kwargs["api_key"] = key
    return kwargs


def _phoenix_tracer(settings: Settings, endpoint: str, *, api_key: str = "") -> Tracer:
    del settings
    from openinference.instrumentation.openai import OpenAIInstrumentor
    from phoenix.otel import register

    provider = register(**phoenix_register_kwargs(endpoint, api_key=api_key))
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    tracer = provider.get_tracer("bcra_rag")
    return _OtelTracer(tracer)


def _project_name() -> str:
    import os

    return os.environ.get("PHOENIX_PROJECT_NAME") or "bcra-rag"


class _OtelTracer:
    def __init__(self, tracer: Any) -> None:
        self._tracer = tracer

    def span(self, name: str, layer: str) -> Any:
        del layer
        return self._tracer.start_as_current_span(name)

    def record_retriever(self, query: str, hits: Sequence[Chunk]) -> None:
        try:
            with self.span("retrieve", "retrieve") as span:
                setter = getattr(span, "set_attribute", None)
                if not callable(setter):
                    return
                for key, value in retriever_attributes(query, hits).items():
                    setter(key, value)
        except Exception:
            return


def retriever_attributes(query: str, hits: Sequence[Chunk]) -> dict[str, object]:
    attrs: dict[str, object] = {
        "openinference.span.kind": "RETRIEVER",
        "input.value": query[:_CONTENT_LIMIT],
    }
    for index, chunk in enumerate(hits):
        doc_id = str(chunk.metadata.get("doc_id") or chunk.chunk_id)
        attrs[f"retrieval.documents.{index}.document.id"] = doc_id
        attrs[f"retrieval.documents.{index}.document.content"] = chunk.text[:_CONTENT_LIMIT]
        attrs[f"retrieval.documents.{index}.document.score"] = float(
            chunk.metadata.get("score") or 0.0
        )
    return attrs
