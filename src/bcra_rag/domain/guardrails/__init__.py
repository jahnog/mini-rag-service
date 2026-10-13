"""Checks that run around one chat turn.

Input and retrieve stop after an enforced block. Output always runs; only an
enforced block replaces the answer. "Generate" is a log row written when the
model is called. It is not one of the checks listed in guardrails/policy.yaml.
"""

from __future__ import annotations

from bcra_rag.domain.guardrails.pipeline import (
    GuardrailPipeline,
    NoOpTracer,
    TracedRail,
    span_id_hex,
    step,
)
from bcra_rag.domain.guardrails.types import (
    Policy,
    RailContext,
    RailResult,
    Tracer,
)

__all__ = [
    "GuardrailPipeline",
    "NoOpTracer",
    "Policy",
    "RailContext",
    "RailResult",
    "TracedRail",
    "Tracer",
    "span_id_hex",
    "step",
]
