## Context

See proposal.md Why and the delta specs under `specs/` for optional collector API-key auth and fail-open L1 write.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index, Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app` / `build_evals`; no DI container.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session (last six messages), one worker, `/clear`.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions). API unit `EnvironmentFile` is the install dir `.env`.

Chat traces already call `phoenix.otel.register` from `adapters/otel.py` when `PHOENIX_COLLECTOR_ENDPOINT` is in the process environment. L1 annotations already construct `phoenix.client.Client(base_url=...)` from `EvalSettings.phoenix_collector_endpoint`. Neither path passes a key.

## Goals / Non-Goals

**Goals:**

- Pass `PHOENIX_API_KEY` into `register()` and `Client()` when non-empty.
- Keep the key optional so local `uvx` Phoenix on loopback still works.
- Keep fail-open. Unit tests; `src` coverage >= 80%.

**Non-Goals:**

- Phoenix fields on chat `Settings`.
- Making the key mandatory when the collector is set.
- `PHOENIX_CLIENT_HEADERS` / Phoenix Cloud legacy `api_key=` header.
- Promoting `arize-phoenix-otel` / `arize-phoenix-client` out of extras.
- The PyPI package named `phoenix` (2013 Habbo client). It must not be a required dependency.

## Decisions

### Decision: optional Bearer key on both export paths

`register(api_key=...)` and `Client(api_key=...)` send `Authorization: Bearer <key>`. Empty string is omitted (`None` / kwargs dropped) so we never send `Bearer `.

Chat tracer reads `PHOENIX_API_KEY` from `os.environ` (same as the collector URL). Dump-host systemd `EnvironmentFile` populates that. Laptop chat traces still need the vars exported (pre-existing collector limitation).

L1 REST sink reads `EvalSettings.phoenix_api_key` (pydantic `.env`). `build_evals` also passes that key into `build_tracer` so laptop L1 traces authenticate without exporting.

Alternatives: rely only on SDK env auto-read (misses pydantic `.env` for `Client`); put Phoenix fields on chat `Settings` (breaks the evals/chat split).

### Decision: do not add the `phoenix` PyPI package

Extras stay `otel` (`arize-phoenix-otel`) and `phoenix-evals` (`arize-phoenix-client`). Revert any `phoenix>=0.9.1` required dep: that name is a different project and shadows `phoenix.otel` / `phoenix.client`.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Structured JSON; FastAPI; prompt with last_refresh / to_as_of | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters | Recommender |
| Vector search; parent = get_section | Second index |

### Decision: Slip order

1. Pass `PHOENIX_API_KEY` on OTEL register and L1 Client
2. Env examples + README How to run
3. Unit tests (kwargs helper; sink constructor; EvalSettings)

Never cut: optional key, fail-open, no live collector in CI, no required `phoenix` package. Deontic scan stays slip-first (not this change).

## Risks / Trade-offs

- [Empty `api_key=""` sends `Bearer `] → omit the kwarg / pass `None`.
- [Developer `.env` leaks into pytest via SDK auto-read] → tests `delenv` / set `PHOENIX_API_KEY`.
- [Wrong `phoenix` package shadows Arize] → revert required dep; keep extras.
- [Laptop uvicorn still misses `.env` Phoenix vars] → same as collector URL today; document; do not add chat Settings fields.

## Migration Plan

No dump or index migration. Operators set `PHOENIX_API_KEY` in `.env` (local copy of `.env.example`, dump-host copy of `deploy/env.remote.example`). Existing `.env` files are not overwritten by deploy. Rollback: revert; leftover `PHOENIX_API_KEY` is ignored.

## Open Questions

None.
