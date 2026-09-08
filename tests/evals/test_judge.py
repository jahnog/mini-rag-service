from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from bcra_rag.evals.adapters.judge_phoenix import _PROMPTS, PhoenixJudge, _label
from bcra_rag.evals.settings import EvalSettings


class _FakeCompletions:
    def __init__(self, content: str, prompt_tokens: int = 3, completion_tokens: int = 5) -> None:
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
            usage=SimpleNamespace(
                prompt_tokens=self.prompt_tokens,
                completion_tokens=self.completion_tokens,
            ),
        )


class _FakeClient:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def test_judge_label_parses_json_and_tokens() -> None:
    assert _label('{"label": "yes"}') == "yes"
    assert _label("the answer is no") == "no"
    assert _label("not json") == "no"


def test_brace_in_answer_does_not_crash_judge() -> None:
    completions = _FakeCompletions('{"label": "yes"}')
    judge = PhoenixJudge(
        EvalSettings(_env_file=None, judge_api_key="k"),
        client=_FakeClient(completions),
    )
    score = judge.classify(
        "faithfulness",
        {"answer": "usa {json} en la cláusula", "context": "x"},
    )
    assert score.value == 1.0
    prompt = str(completions.kwargs["messages"][0]["content"])
    assert "usa {json} en la cláusula" in prompt


def test_judge_sends_reasoning_effort_and_counts_usage() -> None:
    completions = _FakeCompletions('{"label": "no"}', prompt_tokens=11, completion_tokens=7)
    judge = PhoenixJudge(
        EvalSettings(_env_file=None, judge_api_key="k", judge_reasoning_effort="none"),
        client=_FakeClient(completions),
    )
    score = judge.classify("answer_relevancy", {"question": "q", "answer": "a"})
    assert score.value == 0.0
    assert completions.kwargs["extra_body"]["reasoning_effort"] == "none"
    assert judge.calls == 1
    assert judge.tokens_in == 11
    assert judge.tokens_out == 7


def test_judge_prompts_are_spanish_first() -> None:
    joined = " ".join(_PROMPTS.values())
    assert "¿" in joined or "Responde" in joined
    assert "Pregunta" in _PROMPTS["answer_relevancy"] or "pregunta" in _PROMPTS["answer_relevancy"]
