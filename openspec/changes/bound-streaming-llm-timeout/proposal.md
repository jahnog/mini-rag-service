## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Production smoke against the public process failed `POST /chat` with Apache HTML 502 after ~180s while the one worker was still streaming a thinking trace: the configured language-model timeout is an idle-between-chunks cap, so tokens keep the call alive past the reverse-proxy wait, the one-shot HTTP body never starts, and the smoke client retries into that same busy worker. A staff user on the observatory websocket can still be watching thinking. The suite must still require a cited Comunicación A 3500, not a faster silencio.

## What Changes

Nothing is **BREAKING** for cookies, the observatory contract, or the default test command.

- A language-model call SHALL be bounded **wall-clock** for the whole `complete` (including a streaming thinking trace). On expiry the turn SHALL be silencio with abstain reason that the model was unavailable, empty citations, structured HTTP 200, and MUST NOT parse a partial stream into CAMEX text.
- The default bound stays 60 seconds. Operators who enable thinking SHALL set `LLM_TIMEOUT_S` below the reverse-proxy wait (and high enough for a named Com. A turn).
- Production-smoke `POST /chat` SHALL NOT retry a slow proxy 502 into a still-running generate. A fast 502 MAY retry once. Named A 3500 still fails closed on silencio.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `platform`: language-model timeout is wall-clock for the whole call, including a streaming thinking trace; timeout still yields silencio and empty citations from the serving process.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- HTTP SSE / streaming the JSON answer.
- A `reasoning_effort` setting or disabling xAI thinking in-app.
- Extra uvicorn workers, `--proxy-headers`, or a worker-kill timeout.
- Changing global Apache `Timeout` or committing reverse-proxy overlays (private layout).
- Playwright / Gradio in production smoke.
- Weakening named A 3500 fail-closed (including `llm_unavailable`).
- Changing the spec default of 60 seconds.
- A git-flow version bump.
- Always-notify cron mail (sibling change).

## Impact

- `generate_from_context` / L1 `run_generation` wrap `complete`; OpenAI adapter keeps the idle socket cap.
- Production-smoke HTTP helper retry policy; unit tests with fakes/`respx`.
- README Debug, `.env.example`, `deploy/env.remote.example` on `LLM_TIMEOUT_S` vs reverse-proxy wait. No new command fence.
- Default `uv run pytest -q` and CI stay fake-only. `src` coverage >= 80%. Do not run `--run-prod-smoke` in CI.
- Dump-host `LLM_TIMEOUT_S` and BCRA `ProxyTimeout` stay operator overlays; laptop cron stays 15m.
