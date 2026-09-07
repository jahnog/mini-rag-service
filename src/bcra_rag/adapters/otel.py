from __future__ import annotations

from typing import Any

from bcra_rag.domain.guardrails.pipeline import NoOpTracer
from bcra_rag.domain.guardrails.types import Tracer
from bcra_rag.settings import Settings


def build_tracer(settings: Settings) -> Tracer:
    endpoint = _collector_endpoint()
    if not endpoint:
        return NoOpTracer()
    try:
        return _phoenix_tracer(settings, endpoint)
    except Exception:
        return NoOpTracer()


def _collector_endpoint() -> str:
    import os

    return (os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") or "").strip()


def _phoenix_tracer(settings: Settings, endpoint: str) -> Tracer:
    del settings
    from openinference.instrumentation.openai import OpenAIInstrumentor
    from phoenix.otel import register

    provider = register(
        project_name=_project_name(),
        endpoint=endpoint,
        protocol="http/protobuf",
        batch=True,
    )
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
