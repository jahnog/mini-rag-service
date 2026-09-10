from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bcra_rag.adapters.turn_eval import (
    OpenAITurnEvaluator,
    _JudgeEnv,
    build_turn_evaluator,
)
from bcra_rag.domain.turn_eval import NoOpTurnEvaluator, TurnScores
from bcra_rag.settings import Settings


class _FakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self.contents = list(contents)
        self.kwargs: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs.append(kwargs)
        text = self.contents.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
        )


class _FakeClient:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


@pytest.mark.asyncio
async def test_noop_scores_are_empty() -> None:
    scores = await NoOpTurnEvaluator().score(
        question="q", answer="a", context="c"
    )
    assert scores == TurnScores()
    assert scores.as_dict() == {}


def test_build_turn_evaluator_off_without_flag(tmp_path) -> None:
    evaluator = build_turn_evaluator(
        Settings(data_dir=tmp_path, chat_turn_evals=False, _env_file=None)
    )
    assert isinstance(evaluator, NoOpTurnEvaluator)


def test_build_turn_evaluator_off_without_key(tmp_path) -> None:
    evaluator = build_turn_evaluator(
        Settings(data_dir=tmp_path, chat_turn_evals=True, _env_file=None),
        env=_JudgeEnv(_env_file=None, judge_api_key="", llm_api_key=""),
    )
    assert isinstance(evaluator, NoOpTurnEvaluator)


@pytest.mark.asyncio
async def test_openai_turn_evaluator_yes_no() -> None:
    completions = _FakeCompletions(['{"label": "yes"}', '{"label": "no"}'])
    evaluator = OpenAITurnEvaluator(
        _JudgeEnv(_env_file=None, judge_api_key="k"),
        client=_FakeClient(completions),
    )
    scores = await evaluator.score(
        question="q", answer="a", context="cláusula"
    )
    assert scores.faithfulness == 1.0
    assert scores.answer_relevancy == 0.0
    assert len(completions.kwargs) == 2


@pytest.mark.asyncio
async def test_openai_turn_evaluator_skips_faithfulness_without_context() -> None:
    completions = _FakeCompletions(['{"label": "yes"}'])
    evaluator = OpenAITurnEvaluator(
        _JudgeEnv(_env_file=None, judge_api_key="k"),
        client=_FakeClient(completions),
    )
    scores = await evaluator.score(question="q", answer="a", context="  ")
    assert scores.faithfulness is None
    assert scores.answer_relevancy == 1.0
    assert len(completions.kwargs) == 1
