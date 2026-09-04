from __future__ import annotations

import json
import re
from typing import Any, Literal

from bcra_rag.domain.urls import TO_DOC_ID, normalize_comm_id
from bcra_rag.schemas import Citation, Finding, LlmDraft
from bcra_rag.settings import Settings

TO_ID_RE = re.compile(r"\btexto_ordenado\b", re.IGNORECASE)
NAMED_A_RE = re.compile(
    r"(?:comunicaci[oó]n\s+)?(?:com\.?\s*)?\"?A\"?[\s-]*(\d{1,5})\b",
    re.IGNORECASE,
)
SYSTEM_PROMPT = (
    "Respond only with JSON keys answer, finding, citations. "
    "citations is an array of objects {id, tipo, punto, snippet}. "
    "id is a dump document id (A8359 or texto_ordenado), never a chunk id. "
    "tipo is TO for the texto ordenado and A for Comunicaciones A. "
    "finding is one of obligacion, permiso, prohibicion, "
    "definicion, procedimiento, silencio. "
    "Quoted clauses stay in Spanish. "
    "Include a Fuente: line in answer when citations exist."
)


def parse_llm_draft(raw: str) -> LlmDraft:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("LLM draft is not a JSON object")
    finding_raw = payload.get("finding")
    if finding_raw is None:
        finding = Finding.SILENCIO
    else:
        try:
            finding = Finding(str(finding_raw))
        except ValueError:
            finding = Finding.SILENCIO
    return LlmDraft.model_validate(
        {
            "answer": payload.get("answer"),
            "finding": finding,
            "citations": _coerce_citations(payload.get("citations")),
        }
    )


def _coerce_citations(raw: object) -> list[Citation]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [_citation(doc_id) for doc_id in _ids_from_text(raw)]
    if not isinstance(raw, list):
        return []
    citations: list[Citation] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            for doc_id in _ids_from_text(item):
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                citations.append(_citation(doc_id))
            continue
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id")
        if not isinstance(raw_id, str):
            continue
        parsed_id = _dump_id_from_token(raw_id)
        if parsed_id is None or parsed_id in seen:
            continue
        seen.add(parsed_id)
        citations.append(_citation(parsed_id, item))
    return citations


def _dump_id_from_token(raw: str) -> str | None:
    text = raw.strip()
    if text.lower() == TO_DOC_ID:
        return TO_DOC_ID
    if ":" in text:
        return None
    try:
        return normalize_comm_id(text)
    except ValueError:
        return None


def _ids_from_text(text: str) -> list[str]:
    found: list[str] = []
    if TO_ID_RE.search(text):
        found.append(TO_DOC_ID)
    for match in NAMED_A_RE.finditer(text):
        doc_id = normalize_comm_id(match.group(1))
        if doc_id not in found:
            found.append(doc_id)
    return found


def _tipo_for(doc_id: str) -> Literal["A", "TO"]:
    return "TO" if doc_id == TO_DOC_ID else "A"


def _citation(doc_id: str, extra: dict[str, Any] | None = None) -> Citation:
    payload: dict[str, Any] = {"id": doc_id, "tipo": _tipo_for(doc_id)}
    if extra:
        for key in ("fecha", "punto", "snippet", "url"):
            value = extra.get(key)
            if value not in (None, ""):
                payload[key] = value
    return Citation.model_validate(payload)


class LlmAdapter:
    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client
        self.calls: list[str] = []

    def _client_or_create(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._settings.llm_api_key,
                base_url=self._settings.llm_base_url,
            )
        return self._client

    async def complete(self, prompt: str) -> LlmDraft:
        self.calls.append(prompt)
        client = self._client_or_create()
        response = await client.chat.completions.create(
            model=self._settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return parse_llm_draft(raw)
