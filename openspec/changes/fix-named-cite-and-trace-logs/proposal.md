## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Production smoke against the public process failed in two independent ways: named Comunicación A 3500 came back `silencio` with `cite-or-abstain` after a successful fetch, and the collector poll saw no `chat.turn` spans because the serving process fail-opens to a silent no-op tracer. Operators cannot tell from `chat.log` whether the model paraphrased a snippet, omitted ids, or never exported traces.

## What Changes

Nothing is **BREAKING** for `POST /chat` cookies, the observatory, or the default test command.

- After a **named** Comunicación fetch, if the draft is not native silencio and the model already named that dump id (citation id or `Fuente:` / id in the answer), the process SHALL publish a verbatim snippet from the fetched section instead of abstaining on a paraphrased or empty snippet. Vigente and similar routes keep strict cite-or-abstain.
- Each `chat_turn` log line SHALL include retrieval route, named id when present, draft finding and citation ids, per-citation cite failures (from the **model** snippets, before empty-snippet fill), and whether named-fetch salvage ran. Thinking, prompt, and secret-shaped tokens stay out.
- Process start SHALL log whether the tracer is enabled or disabled (reason: unset endpoint, missing otel extra, or register failure). Collector host and project only; no API key.
- The serving process SHALL append compact per-span records to a dump-host traces file whether or not a collector is configured. Chat stays fail-open if that file cannot be written.
- Production-smoke collector timeout SHALL name the last collector HTTP status (empty 200 vs 401 vs connect error). Tests still fail closed; they MUST NOT skip `cite-or-abstain`.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `query-answering`: named-fetch snippet salvage when the model already names the dump id.
- `query-logging`: reconstructable cite-or-abstain and named-fetch fields on the chat turn; tracer enabled/disabled at start; compact local traces file.
- `platform`: optional collector stays fail-open; compact local traces SHALL still be written; smoke timeout names collector HTTP status (test-only helper, documented here so operators know the fail-closed poll).
- `retrieval`: named Com. A that is in the dump and named by the model SHALL cite that dump id even when the model paraphrases the snippet field.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Weakening cite-or-abstain on vigente or similar routes.
- Attaching a citation when the draft never names the dump id.
- A product-side tracer `flush()` to pass smoke.
- Wrapping `phoenix.otel.register`’s OTLP exporter or adding a second Phoenix.
- Installing the otel extra on the dump-host release pipeline (operator; not this change’s code).
- Reconstructing `get_section` reading order (follow-up).
- A generate retry on cite-or-abstain.
- Changing `LLM_MODEL`.
- Skipping production-smoke `cite-or-abstain`.
- A git-flow version bump.

## Impact

- `AnswerQuery` / citation merge, `chat_turn` payload, `build_tracer` / Tracer adapter, `tests/prod/phoenix.py` timeout text.
- No new RAG port. No new runtime package. Traces file lives under `DATA_DIR/logs/` next to `chat.log`.
- Default `uv run pytest -q` and CI stay fake-only. `src` coverage >= 80%.
- README Debug MAY name the traces file; no new How-to-run command fence.
