"""Checks that run around one chat turn.

Input and retrieve stop after a block. Output always runs; a block there
replaces the answer. "Generate" is a log row written when the model is
called. It is not one of the checks listed in registry.RAILS.
"""

from __future__ import annotations

from bcra_rag.domain.guardrails.pipeline import (
    GuardrailPipeline,
    step,
)
from bcra_rag.domain.guardrails.types import (
    RailContext,
    RailResult,
)

__all__ = [
    "GuardrailPipeline",
    "RailContext",
    "RailResult",
    "step",
]
