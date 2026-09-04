from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Finding(StrEnum):
    OBLIGACION = "obligacion"
    PERMISO = "permiso"
    PROHIBICION = "prohibicion"
    DEFINICION = "definicion"
    PROCEDIMIENTO = "procedimiento"
    SILENCIO = "silencio"


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tipo: Literal["A", "TO"]
    fecha: str | None = None
    punto: str | None = None
    snippet: str = ""
    url: str | None = None


class GuardrailVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: str
    verdict: Literal["pass", "warn", "block"]
    detail: str = ""


class HitScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    score: float = 0.0


class Sidecar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_k: list[HitScore] = Field(default_factory=list)
    citation_coverage: float = 0.0
    grounded: bool = False


class ChatFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: list[str] | None = None
    comm_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    session_id: str | None = None
    k: int | None = None
    filters: ChatFilters | None = None


class ChatClearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str


class LlmDraft(BaseModel):
    """Structured generation payload. Extra keys from the model are ignored."""

    model_config = ConfigDict(extra="ignore")

    answer: str
    finding: Finding
    citations: list[Citation] = Field(default_factory=list)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    finding: Finding
    citations: list[Citation] = Field(default_factory=list)
    abstain: bool
    abstain_reason: str | None = None
    last_refresh: str | None = None
    to_as_of: str | None = None
    guardrails: list[GuardrailVerdict] = Field(default_factory=list)
    sidecar: Sidecar = Field(default_factory=Sidecar)
    request_id: str
    session_id: str
    disclaimer: str = ""

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
    embedding_model: str | None = None


def empty_sidecar() -> Sidecar:
    return Sidecar()


def model_has_field(model: type[BaseModel], name: str) -> bool:
    return name in model.model_fields


def dump_public(model: BaseModel) -> dict[str, Any]:
    return model.model_dump()
