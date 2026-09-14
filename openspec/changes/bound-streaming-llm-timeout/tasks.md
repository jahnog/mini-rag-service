## 1. platform — wall-clock language-model timeout

- [x] 1.1 In `generate_from_context`, wrap `llm.complete` with `asyncio.timeout(timeout_s)`. Pass `timeout_s` from `Settings.llm_timeout_s` in `AnswerQuery._respond` and L1 `run_generation`. On `TimeoutError` use the existing silencio / `llm_unavailable` path; do not parse a partial stream. Keep `AsyncOpenAI(timeout=llm_timeout_s)` as the idle socket cap. Do not change the 60s default. Verify `uv run pytest tests/test_answer_query.py tests/evals/test_generate.py tests/test_llm_port.py tests/test_settings.py -q`: a SlowLlm that keeps emitting thinking past a tiny timeout is silencio with empty citations and no CAMEX / exception text; a fast FakeLlm still cites; `llm_timeout_s` default remains 60.

## 2. prod-smoke — fast 502 retry only

- [x] 2.1 In `tests/prod/http_client.py`, retry 502/503/504 at most once and only when that response returned in under `CHAT_FAST_FAIL_S` (~15s). Slow proxy 502 is the failed turn (no second generate). Keep `CHAT_TIMEOUT_S=480` and `CHAT_RETRY_GAP_S` for the fast path. Verify `uv run pytest tests/test_prod_http_client.py -q`: fast 502 then JSON succeeds with two calls; three slow 502s is one call and `ProdHttpError` naming 502; 429 still fail-fast.

## 3. docs

- [x] 3.1 Document in `.env.example`, `deploy/env.remote.example`, and README Debug that `LLM_TIMEOUT_S` is wall-clock for the whole call (thinking included), must be less than the reverse-proxy wait, and thinking-on named Com. A needs more than 60s. No new How-to-run fence. Verify `uv run pytest tests/test_notes.py tests/test_no_private_layout.py tests/test_deploy.py -q` and that tracked files still do not name the public host or overlay path.

## 4. quality gate

- [x] 4.1 Run `uv run ruff check .`, `uv run mypy src`, then `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml`. Fix until green with src coverage >= 80%. Do not run a paid L1 eval. Do not run `--run-prod-smoke` or `--run-live-server` as a CI-blocking task.
