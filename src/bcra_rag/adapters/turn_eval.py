from __future__ import annotations

import json
from typing import Any

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict

from bcra_rag.domain.turn_eval import NoOpTurnEvaluator, TurnEvaluator, TurnScores
from bcra_rag.settings import Settings

log = structlog.get_logger(__name__)

_PROMPTS = {
    "faithfulness": (
        "¿Cada afirmación de la respuesta está respaldada por el contexto? "
        'Responde JSON {{"label": "yes" o "no"}}.\n'
        "Contexto:\n{context}\nRespuesta:\n{answer}"
    ),
    "answer_relevancy": (
        "¿La respuesta aborda la pregunta? "
        'Responde JSON {{"label": "yes" o "no"}}.\n'
        "Pregunta:\n{question}\nRespuesta:\n{answer}"
    ),
}


class _JudgeEnv(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    judge_model: str = "grok-4.3"
    judge_base_url: str = "https://api.x.ai/v1"
    judge_api_key: str = ""
    judge_reasoning_effort: str = "none"
    llm_api_key: str = ""

    def resolved_key(self) -> str:
        return (self.judge_api_key or self.llm_api_key).strip()


def build_turn_evaluator(
    settings: Settings,
    *,
    env: _JudgeEnv | None = None,
    client: Any | None = None,
) -> TurnEvaluator:
    if not settings.chat_turn_evals:
        return NoOpTurnEvaluator()
    resolved = env or _JudgeEnv()
    key = resolved.resolved_key()
    if not key:
        log.info("chat_turn_evals_skipped", reason="no_judge_key")
        return NoOpTurnEvaluator()
    return OpenAITurnEvaluator(resolved, client=client)


class OpenAITurnEvaluator:
    def __init__(self, env: _JudgeEnv, *, client: Any | None = None) -> None:
        from openai import AsyncOpenAI

        self._model = env.judge_model
        self._effort = (env.judge_reasoning_effort or "").strip()
        self._client = client or AsyncOpenAI(
            api_key=env.resolved_key(),
            base_url=env.judge_base_url,
        )

    async def score(
        self, *, question: str, answer: str, context: str
    ) -> TurnScores:
        faithfulness: float | None = None
        relevancy: float | None = None
        try:
            if context.strip():
                faithfulness = await self._classify(
                    "faithfulness", {"context": context, "answer": answer}
                )
            relevancy = await self._classify(
                "answer_relevancy", {"question": question, "answer": answer}
            )
        except Exception:
            log.info("chat_turn_evals_failed")
            return TurnScores()
        return TurnScores(faithfulness=faithfulness, answer_relevancy=relevancy)

    async def _classify(self, name: str, inputs: dict[str, str]) -> float:
        template = _PROMPTS[name]
        prompt = template
        for key, value in inputs.items():
            prompt = prompt.replace("{" + key + "}", value)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self._effort:
            kwargs["extra_body"] = {"reasoning_effort": self._effort}
        response = await _create(self._client, kwargs)
        content = (response.choices[0].message.content or "").strip()
        return 1.0 if _label(content) in {"yes", "faithful", "relevant"} else 0.0


async def _create(client: Any, kwargs: dict[str, Any]) -> Any:
    try:
        from phoenix.trace import suppress_tracing
    except Exception:
        suppress_tracing = None
    create = client.chat.completions.create
    if suppress_tracing is None:
        return await create(**kwargs)
    with suppress_tracing():
        return await create(**kwargs)


def _label(raw: str) -> str:
    text = raw.strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and payload.get("label"):
            return str(payload["label"]).strip().lower()
    except json.JSONDecodeError:
        pass
    lowered = text.lower()
    if "yes" in lowered:
        return "yes"
    return "no"
