## Context

See proposal.md Why. Behavior is in the three delta specs (`evals-l1`, `platform`, `assistant-ui`).

Product runtime already exists: five ports (Catalog, Extractor, Index, Llm, SessionStore); composition root `build_app` / `build_ingest`; ingest/refresh on the dump host; Router (named Com. A / vigente / similarity; chunker B on TO + clean A’s); in-process session; Gradio on FastAPI; guardrail pipeline with optional OTel (`PHOENIX_COLLECTOR_ENDPOINT`) fail-open.

L1 today: `evals/gold.jsonl` (30 rows, no `reference_answer`) → `use_cases/run_l1.py` scores **Router hits only** (citation-id is retrieved dump ids) → `evals/l1.json` with `ragas: null`. `AnswerQuery` always calls `Router.route` before generate. `IndexPort.get_section` returns `str` (~2k without punto). Optional extras: `l1 = ["ragas"]` (unused), `otel`, `phoenix-evals`.

## Goals / Non-Goals

**Goals:**

- Evals as a **vertical module** (`bcra_rag.evals`) with its own composition, domain, ports, adapters, and use cases — not sprinkled under `domain/evals` + `use_cases/run_l1`.
- Two independent eval suites behind a thin operator command, hexagonal inside that vertical.
- Extract generate-from-context so oracle generation never searches (chat kernel owns the helper; evals imports it, not the reverse).
- Phoenix annotations + retriever spans, fail-open, one project.
- Drop the RAGAS extra and the `ragas` JSON key.

**Non-Goals (design-level):**

- Sixth application port on the chat hexagon, DI container, CQRS, Redis.
- Putting eval metrics under `bcra_rag.domain` or rewriting `use_cases/run_l1.py` in place as the home of the feature.
- Reusing `AnswerQuery.run` with a skip-retrieval flag.
- Chat `build_app` importing `bcra_rag.evals`.
- Hardcoding collector hostnames.
- USD cost in the report; `--from-phoenix` as a v1 MUST.
- Changing ingest/refresh, session TTL, or chat `LLM_MODEL`.

## Decisions

### Decision: Evals is a vertical module

New package `bcra_rag.evals`, a full hexagon slice. Chat (`build_app`, `api`, `ui`) and ingest (`jobs`) MUST NOT import it. The repo-root `evals/run_l1.py` stays a thin CLI: load settings, `build_evals()`, run, write JSON.

```
bcra_rag/evals/
  composition.py          # build_evals() — only composition root that wires the judge
  settings.py             # EvalSettings: JUDGE_*, evals_dir (chat Settings stays LLM_*)
  domain/
    types.py              # GoldRow, samples, Score, reports
    metrics/              # one class per metric
  ports/
    judge.py              # Judge
    sink.py               # EvalSink
  adapters/
    judge_phoenix.py
    judge_fake.py
    sink_phoenix.py
    sink_noop.py
  use_cases/
    run_retrieval.py
    run_generation.py
    run_l1.py             # façade (replaces bcra_rag.use_cases.run_l1)
```

Tests live under `tests/evals/`. Default pytest still uses FakeJudge and does not import `phoenix.evals`.

Chat five ports unchanged. `Judge` / `EvalSink` live only in this vertical (same Null Object pattern as `Tracer`, but not on the chat composition root).

`generate_from_context` stays in query-answering (`AnswerQuery` after route). The evals vertical **imports that helper**. `answer_query.py` MUST NOT import `bcra_rag.evals`.

Move (do not leave a second implementation): delete scoring from `bcra_rag.use_cases.run_l1` once the façade lives in the vertical. Keep a one-line re-export only if existing tests need a deprecation shim; prefer updating tests to import the vertical.

Alternatives: `domain/evals` + `adapters/judge_phoenix` + `use_cases/run_l1` (horizontal scatter — rejected); sixth chat port (bloat); separate installable package (YAGNI).

### Decision: Two metric protocols, typed samples

`RetrievalSample` / `GenerationSample`. `RetrievalMetric.score(RetrievalSample) -> Score | None`. `GenerationMetric.score(GenerationSample) -> Score | None`. `None` means skip (do not score 0). One class per metric. `evals.use_cases.run_l1` is a façade: load gold → requested suites → persist `evals/l1.json` → sink.

Retrieval metrics: `HitAtK(5)`, `PrecisionAtK(5)`, `Mrr`, `NdcgAtK(5)` slip-first, `ContextPrecision`, `ContextRecall`, retrieve latency.

Generation metrics: `Faithfulness`, `AnswerRelevancy`, `CitationIdExact`, `CitationPuntoExact`, `CitationSnippetGrounded`, `FindingExact`, generate latency.

Alternatives: one god `EvalSample` with runtime rejects (dirty types); blended overall score (hides which half failed).

### Decision: Do not call AnswerQuery.run for oracle generation

`AnswerQuery._respond` always `Router.route`s (named Com. A wins). Extract `generate_from_context(query, hits, …)` — prompt + `LlmPort.complete` + finding post-check + **output** rails — used after routing in chat and by the generation suite with hits already in hand. Production chat stays retrieve-then-generate. Eval oracle never calls `IndexPort.search` or `Router.route`. Input rails are not in the helper; gold questions that would block are skipped with a reason.

`run_generation_eval` is async (`asyncio.run` from the sync CLI). Tests use pytest-asyncio.

Alternatives: flag on `AnswerQuery.run` (easy to misuse on chat); second LLM adapter (YAGNI).

### Decision: Oracle chunks via get_section, not search

`oracle_chunks(index, gold_row)` in `evals.use_cases` (not a domain ContextProvider protocol, not in chat domain):

- For each gold id: wrap `get_section(id, punto)` as `Chunk` with `doc_id` / `punto` metadata.
- `gold_puntos` apply to `texto_ordenado` only; Comunicaciones A use `get_section(id, None)`.
- Concatenate, cap at `Settings.max_context_chars`.
- Empty gold ids (silencio): empty hits; still generate (model should abstain); skip faithfulness and answer relevancy; score finding exact and citation-id (empty vs empty).
- Gold ids without punto: skip judged faithfulness/relevancy for that row rather than stuffing a TO prefix.

`--generation-context=retrieved` passes retrieval-suite hits by value in the same run.

### Decision: Phoenix evals + grok-4.3, not RAGAS

Delete `l1 = ["ragas"]`. `EvalSettings` in the vertical maps `JUDGE_*` onto an OpenAI-compatible client (`base_url` `https://api.x.ai/v1`, model `grok-4.3`). `JUDGE_API_KEY` falls back to `LLM_API_KEY`. `JUDGE_REASONING_EFFORT` default `none`. Do not require `OPENAI_API_KEY`. Chat `Settings` does not grow judge fields.

- Faithfulness → `FaithfulnessEvaluator`
- Context precision → `RetrievalRelevanceEvaluator` per chunk, then rank-aware fraction relevant (RAGAS context-precision definition). Distinct JSON field from code `precision_at_5`.
- Answer relevancy and context recall → `ClassificationEvaluator` (Spanish-first rubrics). Context recall: each reference sentence attributed to **retrieved** context; skip rows without `reference_answer`.

Missing extra/key: judged block omitted with `skip_reason`; operator command does not crash. `FakeJudge` in tests. Default pytest must not import `phoenix.evals`.

### Decision: One Phoenix project, namespaced annotations

`phoenix.otel.register` is one tracer provider. Canonical project `PHOENIX_PROJECT_NAME=bcra-rag`. Annotation names `retrieval.hit_at_5`, `generation.faithfulness`, … `PHOENIX_EVALS_PROJECT_NAME` optional only if the evals SDK isolates judge traces without replacing the global provider.

OTLP endpoint stays `PHOENIX_COLLECTOR_ENDPOINT` (local loopback or the dump-host collector URL). REST client uses the collector **host**; strip `/v1/traces` and trailing slash in the adapter. Retriever span document text truncated (~get_section size). Fail open: sink errors never fail the JSON write. `NoOpEvalSink` when unset.

Chat + retrieval suite emit OpenInference `RETRIEVER` with `retrieval.documents`. Generation-oracle emits LLM/CHAIN only. Guardrail spans unchanged.

`--from-phoenix` (score live traces) is slip-last / cuttable.

### Decision: Headline citation-id is model cites

Today `run_l1` sets `cited = retrieved`. After this change, flat `citation_id_exact` copies `generation.citation_id_exact`. Retrieval’s comparable number is `hit_at_5`. Nested JSON is canonical; only those three flat aliases for the current accordion.

Slices: by gold `bucket`; value = generation citation-id when generation ran, else retrieval hit@5. Chunking A/B stays a retrieval-side count report (existing `rebuild_structured_slice`).

Tokens: `judge.calls`, `tokens_in`, `tokens_out`. No USD.

### Decision: Settings and CLI

| Env | Default |
|---|---|
| `JUDGE_MODEL` | `grok-4.3` |
| `JUDGE_BASE_URL` | `https://api.x.ai/v1` |
| `JUDGE_API_KEY` | empty → `LLM_API_KEY` |
| `JUDGE_REASONING_EFFORT` | `none` |
| `PHOENIX_COLLECTOR_ENDPOINT` | empty |
| `PHOENIX_PROJECT_NAME` | `bcra-rag` |

Chat `LLM_*` unchanged. Repo-root `evals/run_l1.py` stays the only operator entry (imports `bcra_rag.evals.composition`):

- default: both suites, generation context `oracle`
- `--retrieval-only` / `--generation-only`
- `--generation-context=oracle|retrieved`
- `--deterministic-only`

No HTTP `/evals`. No Gradio Run. Refresh still does not run L1.

### Decision: Ingest, router, session, host refresh (unchanged)

Ingest/refresh still write `data/bcra/current/` + `data/index/` on the dump host. Router still named-fetch / vigente / similarity. Session still in-process, last 6, TTL 1h. Host crontab/compose still owns the index. L1 still operator-only on that same dump.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Structured JSON; FastAPI; prompt with last_refresh / to_as_of | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters | Recommender |
| Vector search; parent = get_section | Second index |

### Decision: Slip order

1. Two suite reports + code metrics + drop `ragas`
2. Retrieval Phoenix metrics
3. Generation oracle + Phoenix faithfulness/relevancy
4. Annotations + RETRIEVER spans
5. `--generation-context=retrieved`, NDCG@5, `--from-phoenix`

Never cut: evals vertical (chat does not import it), independent suites, gold schema with 8–12 references+puntos, CI-no-pay, fail-open collector, citation-id headline as model cites, no RAGAS dependency, oracle generation without search, unit tests, src coverage >= 80%. Deontic scan stays slip-first (not this change).

## Risks / Trade-offs

- [Chat imports evals] → test that `composition.build_app` / `api` / `ui` sources do not mention `bcra_rag.evals`; chat tests pass without the judge extra.
- [AnswerQuery extract regresses chat] → helper used only after route; named-fetch tests stay; no skip-retrieval flag.
- [TO prefix as oracle] → require puntos on reference rows; skip judged gen when no usable clause.
- [Citation-id meaning change] → spec/UI say model cites; hit@5 remains retrieval.
- [Judge cost / rate] → operator-only; effort none; skip judged if no key; document in README.
- [n=30 p95 latency noisy] → ops signal, not a quality gate.
- [Phoenix REST vs OTLP URL] → adapter normalizes host; do not bake hostnames.
- [Global tracer provider] → one project + name prefixes, not two promised projects.
- [Fixture looks real] → unpublished/sample; judged skipped not 0.
- [Snippet grounded vs freeze rewrite] → score after output rails against stuffed context.

## Migration Plan

No dump or index migration. Next `uv sync` drops the ragas extra. Next operator `uv run python evals/run_l1.py` writes nested JSON; shipped fixture stays unpublished until then. Chat answers without collector. Rollback: revert the change; leftover `JUDGE_*` env keys are ignored. Host deploy is existing `./scripts/deploy.sh` (no unit file edits unless `.env` gains judge keys).

## Open Questions

None that change specs. `--from-phoenix` remains slip-last.
