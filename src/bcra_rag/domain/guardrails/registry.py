from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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
from bcra_rag.domain.guardrails.pipeline import GuardrailPipeline
from bcra_rag.domain.guardrails.retrieve import (
    ChunkHygieneRail,
    ChunkInjectionRail,
    ContextBudgetRail,
)
from bcra_rag.domain.guardrails.types import (
    Policy,
    Rail,
)
from bcra_rag.settings import Settings


@dataclass(frozen=True)
class _Deps:
    """What a rail may need besides its class: its enforce flag and the settings."""

    enforce: bool
    settings: Settings


RAIL_BUILDERS: dict[str, Callable[[_Deps], Rail]] = {
    "length": lambda d: LengthRail(d.settings.max_message_chars, enforce=d.enforce),
    "normalize": lambda d: NormalizeRail(enforce=d.enforce),
    "secrets": lambda d: SecretsRail(field="text", enforce=d.enforce),
    "secrets-output": lambda d: SecretsRail(field="answer", enforce=d.enforce),
    "no-advice": lambda d: NoAdviceRail(field="text", enforce=d.enforce),
    "no-advice-output": lambda d: NoAdviceRail(field="answer", enforce=d.enforce),
    "injection": lambda d: InjectionRail(enforce=d.enforce),
    "scope": lambda d: ScopeRail(enforce=d.enforce),
    "chunk-hygiene": lambda d: ChunkHygieneRail(enforce=d.enforce),
    "chunk-injection": lambda d: ChunkInjectionRail(enforce=d.enforce),
    "context-budget": lambda d: ContextBudgetRail(d.settings.max_context_chars, enforce=d.enforce),
    "cite-or-abstain": lambda d: CiteOrAbstainRail(enforce=d.enforce),
    "freeze-honesty": lambda d: FreezeHonestyRail(enforce=d.enforce),
    "prompt-leak": lambda d: PromptLeakRail(enforce=d.enforce),
    "unsafe-output": lambda d: UnsafeOutputRail(enforce=d.enforce),
    "markdown-sanitize": lambda d: MarkdownSanitizeRail(enforce=d.enforce),
}


def assemble_pipeline(
    policy: Policy,
    settings: Settings,
) -> GuardrailPipeline:
    """One rail per enabled entry in guardrails/policy.yaml.

    An unknown rail id raises at startup.
    """
    rails: list[Rail] = []
    for spec in policy.rails:
        if not spec.enabled:
            continue
        builder = RAIL_BUILDERS.get(spec.id)
        if builder is None:
            raise ValueError(f"unknown rail id: {spec.id}")
        rails.append(builder(_Deps(spec.enforce, settings)))
    return GuardrailPipeline(
        rails,
        global_enforce=policy.enforce,
        policy_version=policy.version,
    )
