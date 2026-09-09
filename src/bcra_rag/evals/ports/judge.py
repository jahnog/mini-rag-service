from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from bcra_rag.evals.domain.types import Score


class Judge(Protocol):
    def classify(self, name: str, inputs: Mapping[str, str]) -> Score: ...
