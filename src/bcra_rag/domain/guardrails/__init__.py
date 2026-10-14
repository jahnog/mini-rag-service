"""Checks that run around one chat turn.

Input and retrieve stop after an enforced block. Output always runs; only an
enforced block replaces the answer. "Generate" is a log row written when the
model is called. It is not one of the checks listed in guardrails/policy.yaml.
"""

from __future__ import annotations

from bcra_rag.domain.guardrails.pipeline import (
    GuardrailPipeline,
    step,
)
from bcra_rag.domain.guardrails.types import (
    Policy,
    RailContext,
    RailResult,
)

__all__ = [
    "GuardrailPipeline",
    "Policy",
    "RailContext",
    "RailResult",
    "step",
]
