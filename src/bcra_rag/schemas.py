from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Finding(StrEnum):
    """Six labels. Silencio means the documents do not answer.

    The other five name the clause: duty, permission, prohibition, definition,
    or procedure. demote_finding may still change obligacion or prohibicion
    after the model answers.
    """

    OBLIGACION = "obligacion"
    PERMISO = "permiso"
    PROHIBICION = "prohibicion"
    DEFINICION = "definicion"
    PROCEDIMIENTO = "procedimiento"
    SILENCIO = "silencio"


class Citation(BaseModel):
    """A dump document id, not a chunk id, plus the quote taken from it.

    id is A8359 or texto_ordenado. tipo is A or TO. punto is the numbered clause.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    tipo: Literal["A", "TO"]
    fecha: str | None = None
    punto: str | None = None
    snippet: str = ""
    url: str | None = None


class GuardrailVerdict(BaseModel):
    """One guardrail log row."""

    model_config = ConfigDict(extra="forbid")

    rule: str
    verdict: Literal["pass", "warn", "block", "redact", "skipped"]
    detail: str = ""
    stage: Literal["input", "retrieve", "generate", "output"] = "input"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    session_id: str | None = None


class LlmDraft(BaseModel):
    """The model's JSON before the output rails. Not the chat response.

    Extra keys from the model are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    answer: str
    finding: Finding
    citations: list[Citation] = Field(default_factory=list)
    thinking: str = ""


class ChatResponse(BaseModel):
    """Body the page renders. abstain is true exactly when finding is silencio."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    finding: Finding
    citations: list[Citation] = Field(default_factory=list)
    abstain: bool
    last_refresh: str | None = None
    to_as_of: str | None = None
    guardrails: list[GuardrailVerdict] = Field(default_factory=list)
    request_id: str
    session_id: str
    thinking: str | None = None

    @model_validator(mode="after")
    def _abstain_iff_silencio(self) -> Self:
        if self.abstain != (self.finding is Finding.SILENCIO):
            raise ValueError("abstain must be true if and only if finding is silencio")
        return self


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_refresh: str | None = None
    to_as_of: str | None = None
    last_comm_id: str | None = None
    n_docs: int = 0
    index_ready: bool = False


def model_has_field(model: type[BaseModel], name: str) -> bool:
    return name in model.model_fields


def dump_public(model: BaseModel) -> dict[str, Any]:
    return model.model_dump()
