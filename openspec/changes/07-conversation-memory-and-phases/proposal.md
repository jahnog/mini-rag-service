## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The session store keeps the last three exchanges (`adapters/session_memory.py`), but the language model never sees them: `_compose_followup` (`src/bcra_rag/use_cases/answer_query.py:39,652-658`) only prepends the previous user question when the new message starts with `y|and|ese|esa|eso|that|el punto`, so "¿Y el plazo?" works by regex luck and "¿Cuánto?" does not, and the previous answer is never available to resolve a pronoun. Meanwhile an end user in the Usuario layout sees nothing at all while a turn runs — the pending "Pensando…" row is a thinking region that the end-user layout hides by design — and even staff only see "Pensando…" for the 200 ms retrieval and the seconds-long citation check; the thinking trace re-renders the whole conversation every 0.12 s.

## What Changes

- The prompt SHALL include the last two exchanges of the session as context that is explicitly not a citation source ("Conversación previa (contexto, no fuente)"), truncated per message; cite-or-abstain keeps requiring this-turn ids, so memory cannot invent a circular.
- The follow-up composition used for retrieval SHALL also trigger for short messages (three words or fewer) that name no Comunicación, in addition to the existing prefix regex.
- The turn SHALL report phases (`retrieve`, `generate`, `verify`) through a callback; the interface SHALL show a phase line ("Buscando en el dump…", "Redactando respuesta…", "Verificando citas…") in both layouts while the turn is in flight and SHALL use the phase as the pending thinking-row title in the staff layout.
- Thinking publishes SHALL be throttled to 0.5 s and skipped when the text did not change.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `query-answering`: session memory reaches the prompt; follow-up heuristic; phase callback.
- `assistant-ui`: phase line in both layouts; publish throttle.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Summarising long histories or persisting sessions across restarts.
- Streaming the answer text (rails run after generation).
- Phase events on the HTTP `/chat` stream (keeps JSON-whitespace keepalives).

## Impact

- `src/bcra_rag/use_cases/answer_query.py` (`OnPhase`, `history_block`, `_compose_followup`, `_prompt(history=…)`, `AnswerQuery.run(on_phase=…)`), `src/bcra_rag/api/handle.py` (pass-through), `src/bcra_rag/ui/config.py` (phase copy, `append_pending(title=…)`, `THOUGHT_PUBLISH_S`), `src/bcra_rag/ui/gradio_app.py` (`iter_observatory_turn` 11th output, `#turn-phase` Markdown), `src/bcra_rag/ui/observatory.css` (`#turn-phase` style).
- Tests: `tests/test_answer_query.py`, `tests/test_ui.py` (fake `run_turn` signatures gain `on_phase=None`; tuple length 11), `tests/test_chat_api.py` untouched.
- No command change.
