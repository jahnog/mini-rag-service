from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from bcra_rag.domain.models import Chunk
from bcra_rag.schemas import Citation, Finding, GuardrailVerdict, LlmDraft

Stage = Literal["input", "retrieve", "generate", "output"]
Verdict = Literal["pass", "warn", "block", "redact", "skipped"]
ChunkAction = Literal["keep", "redact", "drop"]


@dataclass
class RailPatch:
    raw: str | None = None
    text: str | None = None
    answer: str | None = None
    finding: Finding | None = None
    citations: list[Citation] | None = None
    hits: list[Chunk] | None = None
    dropped_ids: list[str] | None = None


@dataclass
class RailResult:
    """One guardrail log row. Verdicts are pass, warn, block, redact, or skipped."""

    rule: str
    stage: Stage
    verdict: Verdict
    detail: str = ""
    patch: RailPatch | None = None

    def to_verdict(self) -> GuardrailVerdict:
        return GuardrailVerdict(
            rule=self.rule,
            verdict=self.verdict,
            detail=self.detail,
            stage=self.stage,
        )


def first_block(results: Sequence[RailResult]) -> RailResult | None:
    """The first rail that blocked."""
    return next((r for r in results if r.verdict == "block"), None)


@dataclass
class ChunkResult:
    action: ChunkAction
    chunk: Chunk
    detail: str = ""


@dataclass
class RailContext:
    """Mutable turn state the rails read and patch.

    raw is this utterance. text may be the follow-up glued onto the previous
    question. hits are the passages search returned.
    """

    raw: str
    text: str
    hits: list[Chunk] = field(default_factory=list)
    draft: LlmDraft | None = None
    answer: str = ""
    finding: Finding = Finding.SILENCIO
    citations: list[Citation] = field(default_factory=list)
    turn_ids: set[str] = field(default_factory=set)
    dump_ids: set[str] = field(default_factory=set)
    last_refresh: str | None = None
    to_as_of: str | None = None
    delimiter: str = ""
    dropped_ids: list[str] = field(default_factory=list)
    retrieval_route: str | None = None
    named_id: str | None = None
    section_chars: int | None = None
    draft_citation_ids: list[str] = field(default_factory=list)
    cite_failures: list[dict[str, str]] | None = None
    salvage: str | None = None
    followup: bool = False


class Rail(Protocol):
    id: str
    stage: Stage

    def run(self, ctx: RailContext) -> RailResult: ...
