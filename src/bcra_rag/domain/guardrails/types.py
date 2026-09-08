from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from bcra_rag.domain.models import Chunk
from bcra_rag.schemas import Citation, Finding, GuardrailVerdict, LlmDraft

Stage = Literal["input", "retrieve", "generate", "output"]
Verdict = Literal["pass", "warn", "block", "redact", "skipped"]
ChunkAction = Literal["keep", "redact", "drop"]


@dataclass
class RailConfig:
    id: str
    stage: Stage
    enabled: bool = True
    enforce: bool = True
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    version: int = 2
    enforce: bool = True
    rails: list[RailConfig] = field(default_factory=list)


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
    rule: str
    stage: Stage
    verdict: Verdict
    detail: str = ""
    enforced: bool = True
    would_block: bool = False
    latency_ms: float = 0.0
    metrics: dict[str, object] = field(default_factory=dict)
    rewrite: str | None = None
    patch: RailPatch | None = None

    def to_verdict(self) -> GuardrailVerdict:
        return GuardrailVerdict(
            rule=self.rule,
            verdict=self.verdict,
            detail=self.detail,
            stage=self.stage,
            enforced=self.enforced,
            would_block=self.would_block,
        )


@dataclass
class ChunkResult:
    action: ChunkAction
    chunk: Chunk
    detail: str = ""


@dataclass
class RailContext:
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


class Rail(Protocol):
    id: str
    stage: Stage
    enforce: bool

    def run(self, ctx: RailContext) -> RailResult: ...


class InjectionBackend(Protocol):
    def score(self, text: str) -> tuple[bool, str]: ...


class Tracer(Protocol):
    def span(self, name: str, layer: str) -> Any: ...

    def record_retriever(self, query: str, hits: Sequence[Chunk]) -> None: ...
