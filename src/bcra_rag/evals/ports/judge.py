from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from bcra_rag.evals.domain.types import Score


class Judge(Protocol):
    """Second chat model that only labels the llm metrics. It does not write the answer."""

    def classify(self, name: str, inputs: Mapping[str, str]) -> Score: ...
