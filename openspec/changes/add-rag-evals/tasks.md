## 1. evals vertical

- [x] 1.1 Create package `bcra_rag.evals` with `composition.build_evals`, `EvalSettings` (`JUDGE_*`, `evals_dir`), `ports/judge.py`, `ports/sink.py`, and Null Object sink. Chat `Settings` does not grow judge fields. Verify `uv run mypy src` and that `composition.py` / `api/` / `ui/` sources do not import `bcra_rag.evals`
- [x] 1.2 Add `tests/evals/` and a unit test that `build_app` still answers without importing the evals package. Verify `uv run pytest tests/test_composition.py tests/evals -q` (or the new test file) passes without the judge extra
- [x] 1.3 Move L1 scoring out of `bcra_rag.use_cases.run_l1`; the façade lives in `bcra_rag.evals.use_cases.run_l1`. Thin `evals/run_l1.py` only boots `build_evals()`. Verify the operator script does not import Gradio / `build_app` and existing `tests/test_l1.py` is redirected to the vertical (or replaced by `tests/evals/`)

## 2. evals-l1 domain and code metrics

- [x] 2.1 In `bcra_rag.evals.domain`, add types (`GoldRow`, `RetrievalSample`, `GenerationSample`, `Score`, `SuiteReport`, `EvalReport`) and protocols `RetrievalMetric` / `GenerationMetric`. Verify mypy on `bcra_rag.evals`
- [x] 2.2 Implement code retrieval metrics `HitAtK(5)`, `PrecisionAtK(5)`, `Mrr` and retrieve latency in `evals/domain/metrics`; empty gold ids with nonempty hits score 0. Verify `uv run pytest tests/evals -q` covers empty-gold, hit, precision, MRR
- [x] 2.3 Implement code generation metrics `CitationIdExact` (model cites), `CitationPuntoExact` (skip when gold puntos empty), `CitationSnippetGrounded`, `FindingExact` (silencio empty-vs-empty is 1). Verify unit tests: mismatched cites 0; snippet not in context 0; A 9999 finding exact 1
- [x] 2.4 Add `adapters/judge_fake.py` and judged wrappers `ContextPrecision`, `ContextRecall`, `Faithfulness`, `AnswerRelevancy` that return `None` when the row should skip. Verify FakeJudge tests never import `phoenix`

## 3. evals-l1 gold

- [x] 3.1 Add `reference_answer` (Spanish cited-clause + `Fuente:`) and gold puntos on 8–12 answerable rows (definición, obligación, procedimiento, post-to, english). Silencio rows stay without a reference. Verify gold parse tests: 8–12 references, silencio has none, reference rows have puntos

## 4. evals-l1 generate-from-context

- [x] 4.1 Extract `generate_from_context` (prompt + `LlmPort.complete` + finding post-check + output rails) from `AnswerQuery`; chat still routes first. Evals vertical imports the helper; `answer_query` MUST NOT import `bcra_rag.evals`. Verify `uv run pytest tests/test_answer_query.py -q`: named A 3500 still uses the router; helper tests prove no `search` call

## 5. evals-l1 retrieval suite

- [x] 5.1 Add `evals.use_cases.run_retrieval` (Router/index only, never `LlmPort.complete`). Keep A/B chunking slice via existing rebuild helper. Verify unit tests: no LLM call; vigente gold scores hit@5; Banxico/A 9999 empty retrieval

## 6. evals-l1 generation suite

- [x] 6.1 Add `oracle_chunks` and `evals.use_cases.run_generation` using `generate_from_context` (async). Default context oracle. Skip faithfulness/relevancy on silencio and on ids without usable clause. Verify tests: oracle generation does not call `IndexPort.search` or `Router.route`; A 3500 oracle uses that extract; A 9999 skips judged gen and scores finding exact

## 7. evals-l1 façade, JSON, extras

- [x] 7.1 Façade `evals.use_cases.run_l1`: requested suites → nested `retrieval` / `generation` / `judge` JSON; drop `ragas` key; flat aliases `citation_id_exact` (from generation), `hit_at_5`, `mrr`; skipped suites have reason not zeros; CLI flags `--retrieval-only` / `--generation-only` / `--generation-context` / `--deterministic-only`. Verify dry FakeIndex run writes the schema, fixture still unpublished/sample, no `ragas` key. Do not run a paid L1 eval
- [x] 7.2 Remove `l1 = ["ragas"]` from `pyproject.toml`; extend `phoenix-evals` extra with `arize-phoenix-evals` and `arize-phoenix-client` if missing. Document `JUDGE_*` on `.env.example` (loaded by `EvalSettings`, not chat Settings). Verify `uv run pytest tests/test_settings.py tests/evals -q` and mypy
- [x] 7.3 Implement `evals.adapters.judge_phoenix` mapping `JUDGE_*` to the OpenAI-compatible client (no `OPENAI_API_KEY` required); missing extra/key → skip judged with reason. Verify default pytest does not import `phoenix.evals`. Do not run a paid judge in CI

## 8. platform tracing and sink

- [x] 8.1 Emit OpenInference `RETRIEVER` spans with truncated `retrieval.documents` on chat retrieve and retrieval-suite replay; fail-open. Chat tracer stays in `adapters/otel.py` (not in the evals vertical). Generation-oracle MUST NOT emit a search span. Verify `NoOpTracer` still answers; recording tracer on chat named-fetch sees a retriever span; oracle generation test sees none
- [x] 8.2 Implement `evals.adapters.sink_phoenix`: REST client on collector host (strip `/v1/traces` and trailing slash); namespaced annotations `retrieval.*` / `generation.*`; NoOp when unset; sink errors do not fail JSON write. Verify unit tests: unset collector writes JSON; fake sink failure still writes JSON. Do not require a live collector in CI

## 9. assistant-ui

- [x] 9.1 Update Calidad L1 markdown: two headings (retrieval / generation); skipped suite labeled skipped not 0; keep citation-id, hit@5, A vs B; unpublished/sample banner. UI still only reads the static file. Verify `uv run pytest tests/test_ui.py -q` for fixture sample label, two headings, skipped generation, end-user layout still hides L1

## 10. README and catalog

- [x] 10.1 Update README.md `## How to run` Reports/Debug: evals vertical / operator L1 flags, judged skip, collector via `PHOENIX_COLLECTOR_ENDPOINT` (loopback locally, dump-host URL remotely), `JUDGE_*`, no RAGAS extra, chat does not load evals. Update `scripts/commands.toml` summary if flags changed. Verify `uv run pytest tests/test_notes.py -q` after extending operator bullets
- [x] 10.2 Run `uv run ruff check .`, `uv run mypy src`, `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml` and fix until green with src coverage >= 80%. Do not run a paid L1 eval
