from __future__ import annotations

from collections.abc import Callable

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
from bcra_rag.domain.guardrails.types import Rail
from bcra_rag.settings import Settings

# The ordered guardrail list the chat log shows. This is the only rail-by-rail list.
RAILS: tuple[str, ...] = (
    # Block a question over the character cap, before search.
    "length",
    # Fold unicode and strip invisible characters.
    "normalize",
    # Block an API-key shape on the question.
    "secrets",
    # Block "should I buy dollars". A regulatory "shall" in a circular is not advice.
    "no-advice",
    # Block jailbreak phrasing ("ignore your instructions") on the question.
    "injection",
    # Block a question that is not about BCRA CAMEX.
    "scope",
    # Drop a retrieved passage that itself matches the jailbreak regex.
    "chunk-injection",
    # Strip role markers from a passage. Drop the passage if nothing remains.
    "chunk-hygiene",
    # Keep passages until max_context_chars. Extra tail passages are a redact, not a block.
    "context-budget",
    # Require a quote from this turn's passages. A near-match can be adjusted.
    # No usable citation hides the draft and abstains.
    "cite-or-abstain",
    # Rewrite an unqualified "vigente hoy" so the answer names the dump date.
    "freeze-honesty",
    # Block investment advice in the answer, unless the words are a quote from this turn.
    "no-advice-output",
    # Block an API-key shape in the answer.
    "secrets-output",
    # Block if the answer contains the passage fence or a system-prompt sentence.
    "prompt-leak",
    # Redact ANSI escapes and tool-call tags. This one does not block.
    "unsafe-output",
    # Redact HTML and unsafe links. A clean answer still passes.
    "markdown-sanitize",
)

RAIL_BUILDERS: dict[str, Callable[[Settings], Rail]] = {
    "length": lambda s: LengthRail(s.max_message_chars),
    "normalize": lambda _: NormalizeRail(),
    "secrets": lambda _: SecretsRail(field="text"),
    "secrets-output": lambda _: SecretsRail(field="answer"),
    "no-advice": lambda _: NoAdviceRail(field="text"),
    "no-advice-output": lambda _: NoAdviceRail(field="answer"),
    "injection": lambda _: InjectionRail(),
    "scope": lambda _: ScopeRail(),
    "chunk-hygiene": lambda _: ChunkHygieneRail(),
    "chunk-injection": lambda _: ChunkInjectionRail(),
    "context-budget": lambda s: ContextBudgetRail(s.max_context_chars),
    "cite-or-abstain": lambda _: CiteOrAbstainRail(),
    "freeze-honesty": lambda _: FreezeHonestyRail(),
    "prompt-leak": lambda _: PromptLeakRail(),
    "unsafe-output": lambda _: UnsafeOutputRail(),
    "markdown-sanitize": lambda _: MarkdownSanitizeRail(),
}


def assemble_pipeline(settings: Settings) -> GuardrailPipeline:
    """One rail per entry in RAILS, in that order."""
    return GuardrailPipeline([RAIL_BUILDERS[rail_id](settings) for rail_id in RAILS])
