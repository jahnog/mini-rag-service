## 1. platform

- [x] 1.1 Revert required `phoenix>=0.9.1` from `pyproject.toml` and `uv.lock` if present. Keep extras `otel` and `phoenix-evals`. Verify `pyproject.toml` has no required `phoenix` package and `uv.lock` has no `name = "phoenix"` distribution.
- [x] 1.2 Add `phoenix_register_kwargs` (or equivalent) in `adapters/otel.py`: include `api_key` only when `PHOENIX_API_KEY` or the optional `build_tracer(..., api_key=)` argument is non-empty. Pass those kwargs to `register()`. Verify unit tests with `delenv`/`setenv`: key present → kwargs have `api_key`; empty/unset → no `api_key`; collector unset still returns NoOpTracer (`test_tracer_is_noop_without_collector`).
- [x] 1.3 Document optional `PHOENIX_API_KEY` in `.env.example` (keep the working-tree line; do not restyle other Phoenix keys) and `deploy/env.remote.example` (empty assignment, no `export`). README `## How to run` Debug: one clause that a collector that requires auth uses `PHOENIX_API_KEY`; local `uvx` serve still needs none. No new command fence. Verify `uv run pytest tests/test_notes.py tests/test_deploy.py tests/test_settings.py -q`: README names `PHOENIX_API_KEY`; remote seed has empty `PHOENIX_API_KEY=` and no `export`.

## 2. evals-l1

- [x] 2.1 Add `phoenix_api_key: str = ""` to `EvalSettings`. `PhoenixEvalSink` takes `api_key` and constructs `Client(base_url=..., api_key=key or None)`. `_maybe_sink` and `build_evals` pass the key; `build_tracer` receives `eval_settings.phoenix_api_key`. Verify `uv run pytest tests/evals tests/test_composition.py tests/test_settings.py -q`: EvalSettings loads `PHOENIX_API_KEY`; chat Settings has no Phoenix fields; sink constructor records `api_key`; empty key is `None`; injected client still posts annotations; composition forwards the key to `build_tracer`.
- [x] 2.2 Run `uv run pytest -q` then `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml` and `uv run mypy src`. Fix until green with src coverage >= 80%. Do not run a paid L1 eval.
