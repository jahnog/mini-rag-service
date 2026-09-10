from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any, Literal
from urllib.parse import urlparse

from bcra_rag.domain.urls import TO_DOC_ID, normalize_comm_id
from bcra_rag.ports.llm import OnThinking
from bcra_rag.schemas import Citation, Finding, LlmDraft
from bcra_rag.settings import Settings

TO_ID_RE = re.compile(r"\btexto_ordenado\b", re.IGNORECASE)
NAMED_A_RE = re.compile(
    r"(?:comunicaci[oó]n\s+)?(?:com\.?\s*)?\"?A\"?[\s-]*(\d{1,5})\b",
    re.IGNORECASE,
)
THINK_RE = re.compile(
    r"<(think|thinking)>\s*(.*?)\s*</\1>",
    re.IGNORECASE | re.DOTALL,
)
_OPEN_RE = re.compile(r"<(think|thinking)>", re.IGNORECASE)
_CLOSE_RE = re.compile(r"</(think|thinking)>", re.IGNORECASE)
_TAG_LITERALS = ("<think>", "<thinking>", "</think>", "</thinking>")
_FENCE_RE = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```$",
    re.IGNORECASE | re.DOTALL,
)
_PARTIAL_ANSWER_RE = re.compile(
    r'"answer"\s*:\s*"((?:\\.|[^"\\])*)',
    re.DOTALL,
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
                timeout=self._settings.llm_timeout_s,
            )
        return self._client

    async def complete(
        self,
        prompt: str,
        *,
        on_thinking: OnThinking | None = None,
    ) -> LlmDraft:
        self.calls.append(prompt)
        client = self._client_or_create()
        kwargs: dict[str, Any] = {
            "model": self._settings.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        extra = _thinking_extra_body(
            self._settings.llm_base_url, self._settings.llm_enable_thinking
        )
        if extra is not None:
            kwargs["extra_body"] = extra
        response = await client.chat.completions.create(**kwargs)
        assembler = ThinkAssembler()
        prompt_tokens = 0
        completion_tokens = 0
        async for chunk in _as_chunk_iter(response):
            usage = _usage_from_chunk(chunk)
            if usage is not None:
                prompt_tokens, completion_tokens = usage
            grew = assembler.feed_chunk(chunk)
            if grew and on_thinking is not None:
                visible = _strip_json_payload(
                    assembler.thinking_text(), assembler.body_text()
                ).strip()
                if visible:
                    await on_thinking(visible)
        thinking, raw = assembler.finish()
        draft = parse_llm_draft(raw or "{}")
        return draft.model_copy(
            update={
                "thinking": thinking,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        )


def _usage_from_chunk(chunk: Any) -> tuple[int, int] | None:
    usage = getattr(chunk, "usage", None)
    if usage is None:
        return None
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    if prompt <= 0 and completion <= 0:
        return None
    return prompt, completion


def _is_xai_base(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "x.ai" or host.endswith(".x.ai")


def _thinking_extra_body(base_url: str, enabled: bool) -> dict[str, Any] | None:
    if _is_xai_base(base_url):
        return None
    return {
        "enable_thinking": enabled,
        "chat_template_kwargs": {"enable_thinking": enabled},
    }


def _thinking_and_content(message: Any) -> tuple[str, str]:
    content = getattr(message, "content", None) or ""
    if not isinstance(content, str):
        content = str(content)
    extra = getattr(message, "reasoning_content", None)
    if isinstance(extra, str) and extra.strip():
        return extra.strip(), content
    reasoning = getattr(message, "reasoning", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip(), content
    matches = list(THINK_RE.finditer(content))
    if not matches:
        return "", content
    thinking = "\n\n".join(
        match.group(2).strip() for match in matches if match.group(2).strip()
    )
    remainder = THINK_RE.sub("", content).strip()
    return thinking, remainder


def _incomplete_tag_hold(text: str) -> int:
    lower = text.lower()
    hold = 0
    limit = min(len(lower), 11)
    for size in range(1, limit + 1):
        tail = lower[-size:]
        if any(tag.startswith(tail) for tag in _TAG_LITERALS):
            hold = size
    return hold


def _unfence(text: str) -> str:
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped


def _answer_value(obj: object) -> str | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get("answer")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _decode_json_string(raw: str) -> str:
    try:
        decoded = json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw.replace('\\"', '"').replace("\\n", "\n")
    return decoded if isinstance(decoded, str) else raw


def _partial_json_answer(text: str) -> str | None:
    match = _PARTIAL_ANSWER_RE.search(text)
    if match is None:
        return None
    value = _decode_json_string(match.group(1)).strip()
    return value or None


def unwrap_thinking_text(thinking: str) -> str:
    text = _unfence(thinking)
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    answer = _answer_value(parsed)
    if answer is not None:
        return answer
    start = text.rfind("{")
    while start != -1:
        snippet = text[start:]
        try:
            obj = json.loads(snippet)
        except json.JSONDecodeError:
            start = text.rfind("{", 0, start)
            continue
        answer = _answer_value(obj)
        if answer is not None:
            prefix = text[:start].rstrip()
            return f"{prefix}\n{answer}".strip() if prefix else answer
        break
    if text.lstrip().startswith("{"):
        return _partial_json_answer(text) or ""
    return thinking.strip()


def _strip_json_payload(thinking: str, raw: str) -> str:
    text = unwrap_thinking_text(thinking)
    payload = (raw or "").strip()
    if payload and payload in text:
        text = unwrap_thinking_text(text.replace(payload, ""))
    return text


def _string_attr(obj: Any, name: str) -> str:
    value = getattr(obj, name, None)
    return value if isinstance(value, str) else ""


async def _as_chunk_iter(response: Any) -> AsyncIterator[Any]:
    if hasattr(response, "__aiter__"):
        async for chunk in response:
            yield chunk
        return
    choices = getattr(response, "choices", None) or []
    if not choices:
        return
    message = getattr(choices[0], "message", None)
    if message is None:
        return
    yield _FinishedMessageChunk(message)


class _FinishedMessageChunk:
    def __init__(self, message: Any) -> None:
        self.choices = [_FinishedMessageChoice(message)]


class _FinishedMessageChoice:
    def __init__(self, message: Any) -> None:
        self.delta = None
        self.message = message


class ThinkAssembler:
    def __init__(self) -> None:
        self._thinking: list[str] = []
        self._body: list[str] = []
        self._buf = ""
        self._in_think = False
        self._seen_extras = False

    def thinking_text(self) -> str:
        return "".join(self._thinking)

    def body_text(self) -> str:
        return "".join(self._body)

    def feed_chunk(self, chunk: Any) -> bool:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return False
        choice = choices[0]
        delta = getattr(choice, "delta", None)
        if delta is None:
            message = getattr(choice, "message", None)
            if message is None:
                return False
            thinking, raw = _thinking_and_content(message)
            grew = False
            if thinking:
                self._seen_extras = True
                self._thinking.append(thinking)
                grew = True
            if raw:
                self._body.append(raw)
            return grew
        grew = False
        extra = _string_attr(delta, "reasoning_content")
        reasoning = _string_attr(delta, "reasoning")
        if extra:
            self._seen_extras = True
            self._flush_buf()
            self._thinking.append(extra)
            grew = True
        elif reasoning:
            self._seen_extras = True
            self._flush_buf()
            self._thinking.append(reasoning)
            grew = True
        content = _string_attr(delta, "content")
        if content:
            if self._seen_extras:
                self._flush_buf()
                self._body.append(content)
            elif self._feed_tagged(content):
                grew = True
        return grew

    def finish(self) -> tuple[str, str]:
        self._flush_buf()
        raw = self.body_text().strip()
        thinking = _strip_json_payload(self.thinking_text(), raw)
        return thinking.strip(), raw

    def _flush_buf(self) -> None:
        if not self._buf:
            return
        if self._in_think:
            self._thinking.append(self._buf)
        else:
            self._body.append(self._buf)
        self._buf = ""

    def _feed_tagged(self, chunk: str) -> bool:
        before = self.thinking_text()
        self._buf += chunk
        self._drain_tags()
        return self.thinking_text() != before

    def _drain_tags(self) -> None:
        while self._buf:
            if self._in_think:
                match = _CLOSE_RE.search(self._buf)
                if match:
                    self._thinking.append(self._buf[: match.start()])
                    self._buf = self._buf[match.end() :]
                    self._in_think = False
                    continue
                self._emit_hold(into_thinking=True)
                return
            match = _OPEN_RE.search(self._buf)
            if match:
                self._body.append(self._buf[: match.start()])
                self._buf = self._buf[match.end() :]
                self._in_think = True
                continue
            self._emit_hold(into_thinking=False)
            return

    def _emit_hold(self, *, into_thinking: bool) -> None:
        hold = _incomplete_tag_hold(self._buf)
        emit = self._buf[:-hold] if hold else self._buf
        self._buf = self._buf[-hold:] if hold else ""
        if not emit:
            return
        if into_thinking:
            self._thinking.append(emit)
        else:
            self._body.append(emit)
