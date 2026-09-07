from __future__ import annotations

from collections.abc import Callable

from bcra_rag.domain.guardrails.backends import RegexBackend
from bcra_rag.domain.guardrails.input import (
    InjectionRail,
    LengthRail,
    NoAdviceRail,
    NormalizeRail,
    ScopeRail,
    SecretsRail,
)
from bcra_rag.domain.guardrails.output import (
    CiteOrAbstainRail,
    FreezeHonestyRail,
    MarkdownSanitizeRail,
    PromptLeakRail,
    UnsafeOutputRail,
)
from bcra_rag.domain.guardrails.pipeline import GuardrailPipeline, NoOpTracer, TracedRail
from bcra_rag.domain.guardrails.retrieve import (
    ChunkHygieneRail,
    ChunkInjectionRail,
    ContextBudgetRail,
)
from bcra_rag.domain.guardrails.types import (
    InjectionBackend,
    Policy,
    Rail,
    RailConfig,
    Tracer,
)
from bcra_rag.settings import Settings

Builder = Callable[[RailConfig, Settings, InjectionBackend], Rail]


def _length(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del backend
    return LengthRail(settings.max_message_chars, enforce=spec.enforce)


def _normalize(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return NormalizeRail(enforce=spec.enforce)


def _secrets(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return SecretsRail(field="text", enforce=spec.enforce)


def _secrets_out(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return SecretsRail(field="answer", enforce=spec.enforce)


def _no_advice(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return NoAdviceRail(field="text", enforce=spec.enforce)


def _no_advice_out(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return NoAdviceRail(field="answer", enforce=spec.enforce)


def _injection(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings
    return InjectionRail(backend, enforce=spec.enforce)


def _scope(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return ScopeRail(enforce=spec.enforce)


def _hygiene(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return ChunkHygieneRail(enforce=spec.enforce)


def _chunk_injection(
    spec: RailConfig, settings: Settings, backend: InjectionBackend
) -> Rail:
    del settings
    return ChunkInjectionRail(backend, enforce=spec.enforce)


def _budget(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del backend
    return ContextBudgetRail(settings.max_context_chars, enforce=spec.enforce)


def _cite(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return CiteOrAbstainRail(enforce=spec.enforce)


def _freeze(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return FreezeHonestyRail(enforce=spec.enforce)


def _prompt_leak(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return PromptLeakRail(enforce=spec.enforce)


def _unsafe(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return UnsafeOutputRail(enforce=spec.enforce)


def _markdown(spec: RailConfig, settings: Settings, backend: InjectionBackend) -> Rail:
    del settings, backend
    return MarkdownSanitizeRail(enforce=spec.enforce)


RAIL_BUILDERS: dict[str, Builder] = {
    "length": _length,
    "normalize": _normalize,
    "secrets": _secrets,
    "secrets-output": _secrets_out,
    "no-advice": _no_advice,
    "no-advice-output": _no_advice_out,
    "injection": _injection,
    "scope": _scope,
    "chunk-hygiene": _hygiene,
    "chunk-injection": _chunk_injection,
    "context-budget": _budget,
    "cite-or-abstain": _cite,
    "freeze-honesty": _freeze,
    "prompt-leak": _prompt_leak,
    "unsafe-output": _unsafe,
    "markdown-sanitize": _markdown,
}


def build_injection_backend(policy: Policy) -> InjectionBackend:
    del policy
    return RegexBackend()


def assemble_pipeline(
    policy: Policy,
    settings: Settings,
    tracer: Tracer | None = None,
) -> GuardrailPipeline:
    resolved = tracer or NoOpTracer()
    backend = build_injection_backend(policy)
    rails: list[Rail] = []
    for spec in policy.rails:
        if not spec.enabled:
            continue
        builder = RAIL_BUILDERS.get(spec.id)
        if builder is None:
            raise ValueError(f"unknown rail id: {spec.id}")
        rails.append(TracedRail(builder(spec, settings, backend), resolved))
    return GuardrailPipeline(
        rails, global_enforce=policy.enforce, policy_version=policy.version
    )
