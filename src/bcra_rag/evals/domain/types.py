"""Shapes for the offline L1 suite. The chat page only reads the published file.

Gold is evals/gold.jsonl: a question, the correct document ids, puntos, a
finding, whether the question is answerable, and sometimes a reference answer.

A retrieval sample is what search returned. A generation sample is what the
model wrote given a context. context_source oracle is the labeled clause, so
a bad search does not lower the generation score. retrieved uses the same
run's hits.

kind code is an exact comparison. kind llm asks a separate judge model. A
missing score is a skip, not a zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from bcra_rag.domain.models import Chunk
from bcra_rag.schemas import Citation, Finding

MetricKind = Literal["code", "llm"]


@dataclass(frozen=True)
class GoldRow:
    id: str
    question: str
    gold_ids: list[str]
    gold_puntos: list[str]
    finding: str
    answerable: bool
    bucket: str
    reference_answer: str | None = None


@dataclass
class RetrievalSample:
    gold: GoldRow
    hits: list[Chunk]
    retrieved_ids: list[str]
    latency_ms: float = 0.0
    silencio: bool = False


@dataclass
class GenerationSample:
    gold: GoldRow
    context: list[Chunk]
    context_source: Literal["oracle", "retrieved"]
    answer: str
    citations: list[Citation]
    finding: Finding
    latency_ms: float = 0.0
    usable_context: bool = True


@dataclass(frozen=True)
class Score:
    name: str
    value: float
    kind: MetricKind = "code"
    label: str = ""
    explanation: str = ""


@dataclass
class SuiteReport:
    skipped: bool = False
    skip_reason: str | None = None
    scores: dict[str, float] = field(default_factory=dict)
    n: int = 0
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class EvalReport:
    unpublished: bool
    sample: bool
    retrieval: SuiteReport
    generation: SuiteReport
    judge_skipped: bool = True
    judge_skip_reason: str | None = "no_judge"
    judge_model: str = "grok-4.3"
    judge_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    chunking: dict[str, object] = field(default_factory=dict)
    slices: dict[str, float] = field(default_factory=dict)
    n: int = 0
    phoenix_exported: bool = False
    annotation_span_id: str | None = None


class RetrievalMetric(Protocol):
    name: str
    kind: MetricKind

    def score(self, sample: RetrievalSample) -> Score | None: ...


class GenerationMetric(Protocol):
    name: str
    kind: MetricKind

    def score(self, sample: GenerationSample) -> Score | None: ...
