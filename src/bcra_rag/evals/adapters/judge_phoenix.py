from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from bcra_rag.evals.domain.types import Score
from bcra_rag.evals.settings import EvalSettings

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
    "context_precision": (
        "¿Este fragmento sirve para responder la pregunta? "
        'Responde JSON {{"label": "yes" o "no"}}.\n'
        "Pregunta:\n{question}\nFragmento:\n{chunk}"
    ),
    "context_recall": (
        "¿Esta oración está respaldada por el contexto? "
        'Responde JSON {{"label": "yes" o "no"}}.\n'
        "Oración:\n{sentence}\nContexto:\n{context}"
    ),
}


class PhoenixJudge:
    def __init__(self, settings: EvalSettings, client: Any | None = None) -> None:
        from openai import OpenAI

        self._model = settings.judge_model
        self._effort = (settings.judge_reasoning_effort or "").strip()
        self._client = client or OpenAI(
            api_key=settings.resolved_judge_key(),
            base_url=settings.judge_base_url,
        )
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def classify(self, name: str, inputs: Mapping[str, str]) -> Score:
        template = _PROMPTS.get(name) or _PROMPTS["answer_relevancy"]
        prompt = _fill(template, inputs)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self._effort:
            kwargs["extra_body"] = {"reasoning_effort": self._effort}
        response = self._client.chat.completions.create(**kwargs)
        self.calls += 1
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.tokens_in += int(getattr(usage, "prompt_tokens", 0) or 0)
            self.tokens_out += int(getattr(usage, "completion_tokens", 0) or 0)
        content = (response.choices[0].message.content or "").strip()
        label = _label(content)
        value = 1.0 if label in {"yes", "faithful", "relevant", "correct"} else 0.0
        return Score(name=name, value=value, kind="llm", label=label, explanation=content[:500])


def _fill(template: str, inputs: Mapping[str, str]) -> str:
    filled = template
    for key, value in inputs.items():
        filled = filled.replace("{" + key + "}", value)
    return filled


def _label(raw: str) -> str:
    text = raw.strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and payload.get("label"):
            return str(payload["label"]).strip().lower()
    except json.JSONDecodeError:
        pass
    lowered = text.lower()
    for token in ("yes", "no", "faithful", "unfaithful", "relevant", "irrelevant"):
        if token in lowered:
            return token
    return "no"
