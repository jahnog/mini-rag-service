## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. L1 today scores only retrieval against gold, treats citation-id as retrieved dump ids, and leaves judged quality as `ragas: null`, so staff cannot tell whether a bad answer is a retriever failure or a generator failure, and Phoenix cannot score RAG quality on the traces it already stores.

## What Changes

Nothing is **BREAKING** for `POST /chat`. The static L1 document gains nested `retrieval` and `generation` blocks; flat `citation_id_exact` / `hit_at_5` / `mrr` remain as compatibility copies. The `ragas` key is **removed**.

- A new **evals vertical** (own composition, domain, adapters, use cases), distinct from chat serving and ingest. Chat MUST NOT import evaluation scoring or the judge. The operator command is a thin entry that boots only that vertical.
- Two independent operator eval suites: **retrieval** (no chat LLM) and **generation** (no search). Default run is both; generation context defaults to **oracle** gold clauses, not live retrieval.
- Retrieval publishes hit@5, precision@5, MRR, judged context precision, judged context recall (rows with a written reference), retrieve latency p50/p95. NDCG@5 is slip-first.
- Generation publishes faithfulness, answer relevancy, citation-id exact (headline: ids the model cited), citation-punto exact, citation-snippet grounded, finding exact, generate latency p50/p95.
- Judge is xAI `grok-4.3` via Phoenix evaluators (not the RAGAS library). Judged metrics may be skipped with a reason when the extra or key is missing; code metrics still publish. CI never calls the judge.
- Gold gains optional `reference_answer` on 8–12 answerable rows that also have puntos, so oracle context is a real clause.
- Optional collector export: retriever spans on chat and retrieval replay; namespaced span annotations (`retrieval.*` / `generation.*`); fail-open. One Phoenix project.
- Staff Calidad L1 stays static, collapsed, and shows two headings. A skipped suite is labeled skipped, not scored 0.
- Remove the `ragas` optional extra. Chat language-model setting is unchanged.

## Capabilities

### New Capabilities

- `evals`: operator evaluation as its own vertical — composition, scoring, judge, and collector sink — independent of chat serving and ingest. Chat answering does not load this vertical.

### Modified Capabilities

- `evals-l1`: two independent published blocks; gold reference answers; judged faithfulness / answer relevancy / context precision / context recall via a collector judge (not RAGAS); citation-punto, citation-snippet grounded, finding exact, precision@5, latencies; judged skip with reason; CI still unpaid.
- `platform`: optional collector still fail-open; retrieval MAY be exported as retriever spans; generation-oracle replay MUST NOT emit a retriever search; operator eval MAY attach namespaced annotations; chat process MUST NOT load eval scoring.
- `assistant-ui`: Calidad L1 still static; two headings (retrieval vs generation); skipped suite labeled skipped.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- RAGAS as a library or JSON namespace; DeepEval; TruLens; LangSmith.
- HTTP eval API, Gradio “Run L1”, Phoenix server-side UI evaluators as source of truth.
- Continuous online evals / Arize AX alerting; scoring live collector traces is slip-last.
- Toxicity, PII, bias, or drift judges; HITL; CSAT; agent/tool-selection metrics; a third safety suite (probes stay tests).
- A blended overall RAG score, or generation metrics that call the retriever.
- Changing the chat language-model setting (the judge is a separate setting).
- A sixth application port or a “skip retrieval” flag on the chat request.

## Impact

- New evals vertical (operator-only). Thin CLI still overwrites the static L1 results the UI reads. Gold file, Calidad L1 markdown, package extras, env example, README How to run, TUI command catalog.
- Chat path: generate-from-context after routing (same answers); optional retriever spans. Chat composition does not import the evals vertical. Five ports unchanged.
- Optional extras: drop RAGAS; keep Phoenix evals/client. Existing OpenTelemetry extra stays.
- Judge settings are separate from chat language-model settings. Collector URLs stay env-only.
- Unit tests with fakes; src coverage stays >= 80%. No paid judge in CI.
