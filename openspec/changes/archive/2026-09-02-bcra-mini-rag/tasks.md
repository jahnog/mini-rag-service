## 1. Platform skeleton

- [x] 1.1 Extend the existing `bcra_rag` package from `add-ingest-scripts` (do not `uv init` from scratch) with fastapi, gradio, pytest-bdd in `pyproject.toml` (do not add langgraph). Extend the existing five port Protocols in place: `IndexPort.search` gains metadata filters; `LlmPort` structured complete; `SessionStore` mint/get/append/expire/clear. Do not recreate the Protocols and do not leave Llm/Session as ingest stubs. Keep `build_ingest`. Verify `uv sync` and `uv run ruff check .` succeed
- [x] 1.2 Add `LLM_*`, `DEMO_API_KEY`, structlog `request_id`, max message (default 4000 chars), default k 5 / max k 8, and rate limit (20 / 60s / client) to existing Settings / `.env.example` (keep `EMBEDDING_*`, `DATA_DIR`) and verify mypy on Settings plus unit tests that extra env keys do not break load and those defaults are applied
- [x] 1.3 Add `composition.build_app` and FastAPI `GET /health` returning `last_refresh`, `to_as_of`, `last_comm_id`, `n_docs`, `index_ready` from the same dump ingest wrote (HTTP 200 and `index_ready=false` on empty dump; date fields present as null and n_docs 0; not HTTP 503; embedding model name SHOULD be present) and verify pytest covers those fields plus empty-index 200
- [x] 1.4 Add an API+Gradio compose service on the existing ingest image/volume with a command override (image CMD stays ingest), one replica / one worker, jobs still off default `up`; update README.md `## How to run` for `docker compose up` / the API process; verify `docker compose config` is valid
- [x] 1.5 Keep GitHub Actions `test.yml` pytest `--cov=src` (fail_under 80 on src from pyproject); do not narrow the coverage gate; verify the workflow file exists and does not call a live LLM

## 2. Corpus ingest

Owned by change `add-ingest-scripts`. Do not re-implement catalog, download, classifier, MANIFEST, or ingest/refresh jobs.

- [x] 2.1 After `add-ingest-scripts` is applied, confirm `python -m bcra_rag.jobs.ingest` and `python -m bcra_rag.jobs.refresh` exist, health reads that same dump/index, and this change adds no second catalog adapter; verify those modules import and `GET /health` fields come from the ingest dump

## 3. Retrieval

- [x] 3.1 Chunkers already landed in `add-ingest-scripts`; add any missing TO-like / tiny-punto tests if not present and do not rewrite `FixedChunker` / `StructuredChunker`
- [x] 3.2 On the existing Chroma `IndexPort` (upsert and truncated `get_section` ~2k already exist), implement `search` with metadata filters (`doc_kind`, `fecha`, `numero`); copy MANIFEST `fecha` onto chunks on index repair; verify tests with InMemoryIndex fake plus one Chroma smoke if deps allow, including a repaired document that still filters by fecha
- [x] 3.3 Deterministic router (not a tool-calling agent): alias expand first (MULC → Mercado Único y Libre de Cambios, cepo → restricciones cambiarias, tipo de cambio de referencia kept; A numbers are named fetch), Com. A regex (wins over vigente), vigente-intent whole-word list (`hoy`, `vigente`, `puedo`, `qué exige`, `que exige`, `liquidar`, `today`, `current`, `liquidate`) resolving `to_as_of` to that Comunicación’s fecha or a later A number (never `fecha > "A8307"`), one xref hop if in MANIFEST else silencio only when the asked-for rule depends on the missing target; citation ids are dump ids; verify unit tests for A 9999 silencio, A 3500 fetch with citation id A3500, MULC expansion, truncated extract without punto, successful xref, incidental missing véase not forcing silencio, Spanish “qué se exige hoy para liquidar…” not 2002-only
- [x] 3.4 Serving A/B metadata is already set on ingest upsert; add the L1 A/B batch rebuild helper (not a second live DB) and verify a unit test that serving chunks already carry `chunker` metadata
- [x] 3.5 At query time, skip correlaciones / historial / origen heading or body text unless the query asks for origen, historial, or correlaciones (do not require `doc_part` metadata; do not rewrite chunkers); verify a vigente rule question does not cite correlaciones

## 4. Guardrails

- [x] 4.1 Implement cite-or-abstain, freeze honesty, scope, injection, and no-advice as separate rules returning pass/warn/block. Scope / injection / no-advice block without retrieval or LlmPort. Freeze honesty **rewrites** the visible answer to name `last_refresh` / `to_as_of` and uses `warn` when the draft was unqualified. Cite-or-abstain checks dump document ids. Verify a unit test per rule including weather→silencio and no LlmPort, jailbreak not leaking hidden instructions, and freeze-honesty rewrite + warn vs pass
- [x] 4.2 Optional deontic retry (slip-first) with a test when duty language mismatches finding; if skipped, note in README. Finding demotion without a second LLM call is required in 5.2, not here
- [x] 4.3 Attach sidecar (top-k ids/scores, citation coverage, grounded) on the response object; verify it is present on a fake AnswerQuery result

## 5. Query answering

- [x] 5.1 Pydantic `ChatRequest`/`ChatResponse` (`extra=forbid`) including finding enum, citations (id = dump document id `A8359` or `texto_ordenado`; tipo `A` for Comunicaciones including events, not for TO), guardrails, sidecar, session_id, request_id, last_refresh, to_as_of, abstain true iff finding is silencio; filters `{ tipo[], comm_id?, date_from?, date_to? }`; verify validation tests reject extra fields and `corpus_as_of` is not a field
- [x] 5.2 Deterministic `AnswerQuery` function graph (cap 2 search + 2 fetch; LLM only after routing) + `LlmPort` structured complete + finding post-check that demotes `obligacion`/`prohibicion` without a second `complete()`; FakeLlm tests for in-corpus `Fuente:` line, Spanish quotes on an English question, empty-hits silencio, and a snippet without duty verbs is not `obligacion`
- [x] 5.3 `InMemorySessionStore` last 6 messages, mint session_id, follow-up composed query, TTL 1h / cap 200; verify follow-up still retrieves
- [x] 5.4 `POST /chat`, `POST /chat/clear`, typed `/clear` with no retrieval; if filters are sent, drop mismatching citations (tipo A drops TO) else silencio; requested `k` MUST NOT exceed platform max 8; oversized and blocked turns never hit LlmPort; verify TestClient chat/clear/filter/k-cap
- [x] 5.5 `index_not_ready` path returns silencio without calling LlmPort; verify unit test
- [x] 5.6 Gherkin: cite-or-abstain, no-advice, named A 3500, injection, weather/scope, freeze-honesty dates, follow-up then clear, filter drop

## 6. Assistant UI

- [x] 6.1 Gradio mounted on FastAPI: banner (to_as_of, last_refresh, last A, n_docs, unofficial extract), chat, three answerable canned prompts plus A 9999 silencio, Clear button, State session_id persists across turns until cleared; verify banner props, prompt list, and session_id reuse
- [x] 6.2 Citation inspector (dump id, fecha, punto, snippet, copy-id of dump id e.g. A8359, bcra.gob.ar URL; click updates inspector and does not navigate), abstain banner, and trust panel rendering the per-query guardrail log; verify silencio sets the banner flag, copy-id exposes A8359, and an in-corpus answer shows v1 rules as pass
- [x] 6.3 Calidad L1 accordion starts collapsed and reads static `evals/l1.json` only; if the file is the shipped fixture, the expanded section labels unpublished/sample; verify numbers are not in the main chat column on load, the sample label is shown for the fixture, and it does not call RunL1

## 7. Evals L1 (operator, not CI-blocking)

- [x] 7.1 Author `evals/gold.jsonl` (cap 30) with columns id, question, gold comunicación ids, gold puntos, finding, answerable, and required buckets including A 3500 vs A 8359, A 9999 silencio, and a few English questions that still cite Spanish puntos; verify the file parses and bucket counts meet the spec
- [x] 7.2 `evals/run_l1.py` writes `evals/l1.json` (hit@5, MRR, citation-id exact as headline, optional RAGAS on 8–12 rows with a written reference, A vs B and which documents B covered, slice table). RAGAS is an optional extra, not a runtime/CI dependency. Commit a fixture `evals/l1.json` labeled unpublished/sample so the UI is not empty; verify a dry-run with FakeIndex produces the JSON schema (no paid LLM and no ragas required for this check)
- [x] 7.3 Update README.md `## How to run` for the API process, `docker compose up`, and `evals/run_l1.py`; published-results placeholders marked unpublished until an operator run; keep the catalog-hole note; verify README contains citation-id, last_refresh, 1990–97 hole, and those new commands

## 8. Platform hardening

- [x] 8.1 Per-IP rate limit (20 / 60s), max message length 4000, max k 8, Gradio queue, optional DEMO_API_KEY; verify oversized message never hits LlmPort and a client over the rate is rejected or delayed without a full CAMEX answer
- [x] 8.2 Disclaimer text on every ChatResponse and footer; verify unit test
- [x] 8.3 `uv run pytest -q --cov=src --cov-report=xml` locally; coverage XML exists; fail-under is src >= 80% from pyproject
