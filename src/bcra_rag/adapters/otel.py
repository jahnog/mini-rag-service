from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from bcra_rag.domain.guardrails.pipeline import NoOpTracer
from bcra_rag.domain.guardrails.types import Tracer
from bcra_rag.domain.models import Chunk
from bcra_rag.settings import Settings

_QUERY_LIMIT = 500
_CONTENT_LIMIT = 800
_KIND_FOR_LAYER = {
    "chain": "CHAIN",
    "eval": "EVALUATOR",
    "retriever": "RETRIEVER",
    "input": "GUARDRAIL",
    "retrieve": "GUARDRAIL",
    "generate": "GUARDRAIL",
    "output": "GUARDRAIL",
}


class _PhoenixFileSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    phoenix_collector_endpoint: str = ""
    phoenix_project_name: str = ""
    phoenix_api_key: str = ""


def build_tracer(
    settings: Settings,
    *,
    endpoint: str = "",
    api_key: str = "",
    project_name: str = "",
) -> Tracer:
    resolved = resolve_collector_endpoint(explicit=endpoint)
    if not resolved:
        return NoOpTracer()
    try:
        return _phoenix_tracer(
            settings, resolved, api_key=api_key, project_name=project_name
        )
    except Exception:
        return NoOpTracer()


def resolve_collector_endpoint(
    *,
    explicit: str = "",
    env_file: str | Path | None = ".env",
    allow_env_file: bool | None = None,
) -> str:
    text = (explicit or "").strip()
    if text:
        return text
    env = (os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") or "").strip()
    if env:
        return env
    if allow_env_file is None:
        allow_env_file = not os.environ.get("PYTEST_CURRENT_TEST")
    if not allow_env_file or env_file is None:
        return ""
    try:
        loaded = _PhoenixFileSettings(_env_file=env_file)  # type: ignore[call-arg]
    except Exception:
        return ""
    return (loaded.phoenix_collector_endpoint or "").strip()


def _resolved_api_key(api_key: str = "") -> str:
    explicit = _concrete_secret(api_key)
    if explicit:
        return explicit
    return _concrete_secret(os.environ.get("PHOENIX_API_KEY") or "")


def _concrete_secret(raw: str) -> str:
    text = (raw or "").strip()
    if len(text) >= 3 and text.startswith("${") and text.endswith("}"):
        return ""
    return text


def phoenix_register_kwargs(
    endpoint: str, *, api_key: str = "", project_name: str = ""
) -> dict[str, str | bool]:
    kwargs: dict[str, str | bool] = {
        "project_name": resolve_project_name(explicit=project_name),
        "endpoint": otlp_http_endpoint(endpoint),
        "protocol": "http/protobuf",
        "batch": True,
    }
    key = _resolved_api_key(api_key)
    if key:
        kwargs["api_key"] = key
    return kwargs


def otlp_http_endpoint(endpoint: str) -> str:
    text = endpoint.strip().rstrip("/")
    if text.endswith("/v1/traces"):
        return text
    return f"{text}/v1/traces"


def _phoenix_tracer(
    settings: Settings, endpoint: str, *, api_key: str = "", project_name: str = ""
) -> Tracer:
    del settings
    from openinference.instrumentation.openai import OpenAIInstrumentor
    from phoenix.otel import register

    os.environ.setdefault("OPENINFERENCE_HIDE_EMBEDDING_VECTORS", "true")
    os.environ.setdefault("OPENINFERENCE_HIDE_EMBEDDINGS_VECTORS", "true")
    register_kwargs = phoenix_register_kwargs(
        endpoint, api_key=api_key, project_name=project_name
    )
    provider = register(
        project_name=str(register_kwargs["project_name"]),
        endpoint=str(register_kwargs["endpoint"]),
        protocol="http/protobuf",
        batch=True,
        api_key=(
            str(register_kwargs["api_key"]) if "api_key" in register_kwargs else None
        ),
    )
    instrument_kwargs: dict[str, Any] = {"tracer_provider": provider}
    try:
        from openinference.instrumentation import TraceConfig

        instrument_kwargs["config"] = TraceConfig(
            hide_embedding_vectors=True,
            hide_embeddings_vectors=True,
        )
    except Exception:
        pass
    OpenAIInstrumentor().instrument(**instrument_kwargs)
    tracer = provider.get_tracer("bcra_rag")
    return _OtelTracer(tracer, provider)


def resolve_project_name(
    *,
    explicit: str = "",
    env_file: str | Path | None = ".env",
    allow_env_file: bool | None = None,
) -> str:
    text = (explicit or "").strip()
    if text:
        return text
    env = (os.environ.get("PHOENIX_PROJECT_NAME") or "").strip()
    if env:
        return env
    if allow_env_file is None:
        allow_env_file = not os.environ.get("PYTEST_CURRENT_TEST")
    if not allow_env_file or env_file is None:
        return "bcra-rag"
    try:
        loaded = _PhoenixFileSettings(_env_file=env_file)  # type: ignore[call-arg]
    except Exception:
        return "bcra-rag"
    return (loaded.phoenix_project_name or "").strip() or "bcra-rag"


class _OtelTracer:
    def __init__(self, tracer: Any, provider: Any | None = None) -> None:
        self._tracer = tracer
        self._provider = provider

    def span(self, name: str, layer: str) -> Any:
        kind = _KIND_FOR_LAYER.get(layer, "UNKNOWN")
        return self._tracer.start_as_current_span(
            name,
            attributes={"openinference.span.kind": kind},
        )

    def record_retriever(
        self,
        query: str,
        hits: Sequence[Chunk],
        *,
        route: str = "",
        silencio_reason: str | None = None,
        span: Any = None,
    ) -> None:
        try:
            attrs = retriever_attributes(
                query, hits, route=route, silencio_reason=silencio_reason
            )
            if span is not None:
                _write_span_attrs(span, attrs)
                return
            with self.span("retrieve", "retriever") as opened:
                _write_span_attrs(opened, attrs)
        except Exception:
            return

    def flush(self) -> None:
        provider = self._provider
        if provider is None:
            return
        try:
            provider.force_flush()
        except Exception:
            return

    def record_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            _write_span_attrs(
                span,
                {
                    "metadata.prompt_tokens": int(prompt_tokens),
                    "metadata.completion_tokens": int(completion_tokens),
                    "metadata.total_tokens": int(prompt_tokens) + int(completion_tokens),
                },
            )
        except Exception:
            return

    def record_scores(self, span: Any, scores: Mapping[str, float]) -> None:
        try:
            attrs: dict[str, object] = {
                f"eval.{name}": float(value) for name, value in scores.items()
            }
            _write_span_attrs(span, attrs)
        except Exception:
            return


def retriever_attributes(
    query: str,
    hits: Sequence[Chunk],
    *,
    route: str = "",
    silencio_reason: str | None = None,
) -> dict[str, object]:
    attrs: dict[str, object] = {
        "openinference.span.kind": "RETRIEVER",
        "input.value": query[:_QUERY_LIMIT],
    }
    if route:
        attrs["retrieval.route"] = route
    if silencio_reason:
        attrs["retrieval.silencio_reason"] = silencio_reason
    dump_ids = [
        str(chunk.metadata.get("doc_id") or chunk.chunk_id) for chunk in hits
    ]
    attrs["output.value"] = ",".join(dump_ids) if dump_ids else (silencio_reason or "empty")
    for index, chunk in enumerate(hits):
        doc_id = str(chunk.metadata.get("doc_id") or chunk.chunk_id)
        attrs[f"retrieval.documents.{index}.document.id"] = doc_id
        attrs[f"retrieval.documents.{index}.document.content"] = chunk.text[:_CONTENT_LIMIT]
        attrs[f"retrieval.documents.{index}.document.score"] = float(
            chunk.metadata.get("score") or 0.0
        )
        meta = {
            key: chunk.metadata[key]
            for key in ("punto", "chunker", "doc_kind")
            if chunk.metadata.get(key) not in (None, "")
        }
        if meta:
            attrs[f"retrieval.documents.{index}.document.metadata"] = json.dumps(
                meta, ensure_ascii=False
            )
    return attrs


def _write_span_attrs(span: Any, attrs: Mapping[str, object]) -> None:
    setter = getattr(span, "set_attribute", None)
    if not callable(setter):
        return
    for key, value in attrs.items():
        setter(key, value)
