## Context

See proposal.md Why. Five ports stay five. Guardrail policy unchanged; scope and no-advice still run on the latest utterance alone (`query-answering` "Follow-up composition does not launder scope").

Facts as of this change's writing:
- `FOLLOW_RE` (`answer_query.py:39`), `_compose_followup(message, history)` (`:652-658`); history fetched at `:206` (`history = self._sessions.get(session_id)`) after the prefix rails and before the suffix rails; `SessionStore.get` returns `list[tuple[role, content]]`; `_remember` stores `(user, assistant)` per turn; cap 6 messages (`session_memory.py`).
- `_prompt(question, hits, last_refresh, to_as_of, delim, chunk_chars)` (change 06 shape) builds `Pregunta:` then `Documentos recuperados…`.
- `AnswerQuery.run(request, *, request_id, on_thinking=None, thinking=None)` → `_respond`; `generate_from_context(...)`; `run_prepared_turn`/`handle_turn` (`api/handle.py`) forward keywords.
- UI: `iter_observatory_turn` yields 10-tuples (change 02 order) and calls `run_turn(message=…, session_id=…, on_thinking=…)`; `append_pending(history, user, thinking="")` (`ui/config.py:288-300`) builds the pending row with `THOUGHT_PENDING_TITLE = "Pensando…"`; `THOUGHT_PUBLISH_S = 0.12` (`:227`); `thought_publish_ready` (`:235`). CSS hides thought rows in `layout-user` (`observatory.css:481-487`), so end users see no pending row.
- `tests/test_ui.py:407` asserts the pending title "Pensando…"; the `run_turn` fakes at `:497-690` accept `(*, message, session_id, on_thinking=None)`.
- `named_ids(question)` (`domain/router.py:157`) returns Comunicación ids named in text.

## Goals / Non-Goals

**Goals:** pronoun/ellipsis follow-ups work; the model sees the prior answer as context only; every user sees progress; fewer redraws.
**Non-Goals:** query rewriting with the model; history summarisation.

## Decisions

### Decision: History block in the prompt, marked as non-source

```python
HISTORY_TURNS = 2
HISTORY_MAX_CHARS = 300

def history_block(history: list[tuple[str, str]], *, turns: int = HISTORY_TURNS, max_chars: int = HISTORY_MAX_CHARS) -> str:
    tail = history[-(2 * turns):]
    lines = []
    for role, content in tail:
        label = "Usuario" if role == "user" else "Asistente"
        text = " ".join((content or "").split())[:max_chars]
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join(lines)
```
`_prompt` gains `history: str = ""`; when non-empty it inserts after `Pregunta:\n{question}\n\n`:
`"Conversación previa (contexto, no fuente; no citar de acá):\n{history}\n\n"`. `generate_from_context` gains `history: str = ""`; `_respond` passes `history_block(history)` (the same `history` variable it already fetched). `/clear` empties the store, so the next prompt has no block. The prior assistant text contains a `Fuente:` line and the freeze footer — harmless as context; cite-or-abstain still requires this-turn ids and anchored snippets.

### Decision: Follow-up heuristic

```python
def _is_short_followup(message: str) -> bool:
    words = [w for w in re.split(r"\s+", message.strip()) if w]
    return 0 < len(words) <= 3 and not named_ids(message)
```
`_compose_followup` composes when `FOLLOW_RE.search(message) or _is_short_followup(message)`. Scope/no-advice keep evaluating `ctx.raw` (unchanged).

### Decision: Phase callback with codes, copy in the UI

In `answer_query.py`: `OnPhase = Callable[[str], Awaitable[None]]`; codes `PHASE_RETRIEVE = "retrieve"`, `PHASE_GENERATE = "generate"`, `PHASE_VERIFY = "verify"`. `AnswerQuery.run(..., on_phase: OnPhase | None = None)` → `_respond` emits `await _emit(on_phase, PHASE_RETRIEVE)` right before `Router(...).route`, `generate_from_context` emits `PHASE_GENERATE` before `_complete_with_retry` and `PHASE_VERIFY` before the output rails (`generate_from_context` gains `on_phase: OnPhase | None = None`). `_emit` swallows exceptions from the callback. `run_prepared_turn`/`handle_turn` gain `on_phase: OnPhase | None = None`.

UI (`ui/config.py`):
```python
PHASE_COPY = {
    "retrieve": "Buscando en el dump…",
    "generate": "Redactando respuesta…",
    "verify": "Verificando citas…",
}
THOUGHT_PUBLISH_S = 0.5
```
`append_pending(history, user, thinking="", *, title: str = THOUGHT_PENDING_TITLE)`.

`iter_observatory_turn` adds an `on_phase` closure that stores `phase[0] = PHASE_COPY.get(code, "")` and sets the event; every yield appends an 11th element `_phase_update(text)` = `gr.update(value=text, visible=bool(text))`; the final and error yields pass `""`. Pending rows use `title=phase[0] or THOUGHT_PENDING_TITLE`. The thinking publish path yields only when `latest[0] != last_yielded_trace`. `run_turn(..., on_phase=on_phase)` is passed in both layouts (phases are not a trace).

`build_blocks`: `phase_box = gr.Markdown("", elem_id="turn-phase", visible=False)` placed right after `chatbot` in the stage; appended as the last item of `outputs`; `_clear` returns `*_empty_inspector(), _phase_update("")`. CSS: `#turn-phase` transparent block, `font-size: var(--wl-text-sm)`, `color: var(--wl-muted)`, with the existing `thought-pulse` border animation reused (`border-left: 2px solid var(--wl-gold); padding-left: var(--wl-space-3); animation: thought-pulse 1.4s ease-in-out infinite`), respecting `prefers-reduced-motion`.

### Decision: Throttle

`on_thinking` publishes when `thought_publish_ready(text)` and `now - last_pub >= THOUGHT_PUBLISH_S`, or when `now - last_pub >= 2 * THOUGHT_PUBLISH_S` regardless of break (so a long token stream without breaks still updates). The consumer loop skips yielding when the trace equals the last yielded one.

## Risks / Trade-offs

- [History biases the model toward the previous answer] → the block is labelled non-source; retrieval still runs on the composed query; rails unchanged.
- [Short-question heuristic composes unrelated one-word questions] → only affects the retrieval query; the raw utterance still governs scope; the model gets both.
- [11th output shifts tests that index the tuple] → new element is appended last; existing indexes stay valid.

## Migration Plan

Deploy normally. No settings.

## Open Questions

None.
