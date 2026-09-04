## Context

`add-ingest-scripts` has already landed: package `bcra_rag`, five port Protocols, `jobs.ingest` / `jobs.refresh`, living dump `data/bcra/current/` + `data/index/`. This change adds chat, retrieval callers, guardrails, Gradio on FastAPI, and L1 on that package. Behavior: the six product delta specs in this change. `corpus-ingest` is not re-specified here.

Constraints: Appendix A Python (uv, pydantic v2, async, FastAPI, pytest, structlog); BCRA CAMEX A + `t-excbio.pdf` only; 18–22h is a budget.

Probed 2026-09-02: buscador `POST /api/endpoints/buscador-comunicaciones.php` `mode=tipo-circular&tipo=A&circular=CAMEX` → 992/974 unique PDFs; TO at `https://www.bcra.gob.ar/Pdfs/Texord/t-excbio.pdf` (201 pages, last incorporated A 8307, 25/08/2025). Catalog continues through A 8464 (2026-08-06). Title mix: 14 TO reprints, 227 Adecuaciones, 748 other. CAMEX seq hole 232→314 (1990–97).

## Goals / Non-Goals

**Goals:**

- Thin hexagon with five ports and a composition root (`build_ingest` stays; add `build_app`).
- Chat and retrieval over the living dump produced by `jobs.ingest` / `jobs.refresh`.
- Deterministic router: aliases first; named Com. A → get_section (wins over vigente); vigente tokens → TO ∪ post-TO A’s; else similarity; skip correlaciones/historial/origen at query time unless asked; one xref hop.
- Gradio on FastAPI; in-process session + `/clear`; one worker / one replica.
- L1 as a batch command writing static JSON.

**Non-Goals (design-level):**

- DI container, Redis, CQRS, second UI, LlamaIndex, second FAISS index, multi-query retriever, GHA-hosted Chroma, filling 1990–97.
- LangGraph / a free tool-calling agent.
- Rewriting ingest chunkers or a second catalog pipeline.
- `aliases.json` in the dump tree (in-code alias table only).

## Decisions

### Decision: Five ports, not a god retriever

Keep the existing Protocols; **extend** them (do not recreate, do not leave Llm/Session as ingest stubs):

- `IndexPort.search(query, *, k, filters=...)` — metadata filters (`doc_kind`, `fecha`, `numero`). `get_section` already truncates ~2k when no punto.
- `LlmPort` structured `complete` → `ChatResponse` (not `str`).
- `SessionStore`: mint, get, append, expire, clear; cap 200; TTL 1h.

`CatalogPort` / `ExtractorPort` unchanged. Use cases: `IngestCorpus` (already landed), `AnswerQuery`, `RunL1`. `src/bcra_rag/composition.py` keeps `build_ingest` and adds `build_app`. FastAPI `Depends` calls `build_app`.

Alternatives: LangChain mega-chain (hard to test); extra EmbeddingsPort (YAGNI — Index owns it); LangGraph ReAct agent (would let the LLM skip named-fetch-wins-over-vigente).

### Decision: Chroma on disk, one serving collection

IBM 3 take. FAISS only if Chroma slips. Serving index: chunker B on TO + clean A’s, A on the rest (`chunker` metadata). L1 A/B is a **batch rebuild** of the structured slice, not two live DBs.

Repair-from-disk MUST copy `fecha` from the MANIFEST entry onto chunks. Without that, vigente `fecha` filters fail after an index repair.

### Decision: Chunking A vs B

Already implemented in ingest; do not rewrite `FixedChunker` / `StructuredChunker`.

- A: ~512 / 128 after hyphen-join and running-header strip (`B.C.R.A. EXTERIOR Y CAMBIOS Sección N`).
- B: `Sección N`, `^\d+(\.\d+)*\.?`, Anexo; merge children under ~80 tokens; prepend `heading_path`.
- Serving ids today: A `{doc_id}:{digest}`, B `{doc_id}:{punto}:{digest}`. L1 gold and citation ids key off dump document id + punto, not chunk id.

### Decision: Ingest classification

Corpus ingest is specified in archived `add-ingest-scripts` (atomic checkpoint: extract → index upsert → MANIFEST; refresh refuses until `last_refresh` is set). This change does not re-implement that pipeline.

Retrieval still depends on those dump facts: full extract for every CAMEX A that is not a TO reprint pack; short event docs only for reprint packs; TO is the clause store; post-TO A’s stay full text. Dump tree `data/bcra/current/{MANIFEST.json,NOTES.md,raw/,extract/}` and `data/index/`. Aliases live in code, not `aliases.json`. Operators run `python -m bcra_rag.jobs.ingest` then schedule `jobs.refresh` on the volume host as specified there.

Alternatives considered: dated dump folders (fight cron); GitHub-hosted Chroma (ephemeral runner).

### Decision: AnswerQuery graph (deterministic Python)

Plain function graph. Cap 2 searches + 2 fetches. LLM is **step 9 only** (structured complete). Not a tool-calling agent. LangGraph is not required.

1. `/clear` → SessionStore.clear, no retrieval, no LLM.
2. Input guardrails (scope, injection, no-advice, oversized message). On **block**: finding `silencio`, no search, no fetch, no LLM.
3. Expand aliases on the query text (all search paths). Table:
   - MULC → Mercado Único y Libre de Cambios
   - cepo → restricciones cambiarias
   - tipo de cambio de referencia (kept as a retrieval phrase)
   - Comunicación numbers are **not** aliases (named fetch).
4. Regex `Com\.?\s*"?A"?[\s-]*\d+` → `get_section` if in MANIFEST else silencio. **Named fetch wins over vigente.** Citation id = dump id (`A3500`).
5. Vigente-intent closed list as **whole words/phrases**: `hoy`, `vigente`, `puedo`, `qué exige`, `que exige`, `liquidar`, `today`, `current`, `liquidate` (and no Com. A number named). Resolve `to_as_of` (a Comunicación id, e.g. `A8307`) to that document’s issue date in the dump, or compare Comunicación numbers. Search `doc_kind=texto_ordenado` then `comunicacion` with `fecha` after that date (ISO) **or** `numero` greater than `to_as_of`. Never compare an ISO `fecha` string to `"A8307"`.
6. Else similarity.
7. Drop chunks whose heading or body is correlaciones, origen de las disposiciones, or historial unless the query asks for origen, historial, or correlaciones. Do **not** require ingest `doc_part` metadata (chunkers only tag `cuerpo` / `anexo`).
8. One xref hop if the clause cross-references another Com. A (`véase Com. A`, `ver Comunicación A`, `según Com. A`) and the target is in MANIFEST. If missing: finding `silencio` **only when** the asked-for rule is not already in the retrieved clauses. Incidental véase MUST NOT wipe a sufficient TO answer. Never invent the missing text.
9. Generate structured pydantic (`extra=forbid`). Prompt includes duty-verb examples. Then a **deterministic post-check**: if finding is `obligacion`/`prohibicion` and the cited snippet has no duty language (`deber`, `deberá`, `no podrán`, `queda prohibido`, or a numbered duty), demote to `definicion` / `procedimiento` / `permiso` / `silencio`. No second LLM call. Optional deontic retry stays slip-first. Abstain is true iff finding is `silencio`. Quoted clauses stay Spanish. `Fuente:` line when citations exist. Citation `id` is dump document id (`A8359` or `texto_ordenado`); `tipo` is `A` for Comunicaciones (including reprint `event`) and is not `A` for the TO.
10. Output guardrails (cite-or-abstain, freeze honesty). Cite-or-abstain checks dump document ids, not chunk ids. Freeze honesty **rewrites** the visible answer to name `last_refresh` / `to_as_of` if the draft was unqualified, then `warn`; `pass` only when the draft already qualified. Other v1 rules pass or block.
11. If the request included filters `{ tipo[], comm_id?, date_from?, date_to? }`, drop citations that miss them; if none remain, silencio. tipo `A` keeps `comunicacion` and `event`, drops `texto_ordenado`.

`get_section` without punto: truncated extract (~2k chars), never the whole TO.

`index_not_ready`: silencio with abstain reason `index_not_ready`; no retrieval; no LLM.

Alternatives considered: extra LLM self-query (IBM 4 leave); aliases only on the similarity branch (misses “MULC vigente hoy”); LangGraph agent (violates deterministic named-fetch / vigente).

### Decision: Session memory

Last 6 messages in `InMemorySessionStore`. Gradio `State` holds `session_id`. Follow-up retrieve query = current + previous user text if short / y|and|ese. Cite-or-abstain still applies. TTL 1h, cap 200 sessions. In-process only: compose API **one replica, one worker**. Redis later if multi-worker.

### Decision: Gradio not Next.js

IBM 2 + timebox. OpenAPI remains if a TS client is added later. Project 2 still carries MCP TypeScript.

Banner: unofficial extract, `to_as_of`, `last_refresh`, last Comunicación id, `n_docs`. Chat + 3 answerable canned prompts + A 9999. Citation inspector (copy dump id e.g. `A8359`, bcra.gob.ar URL; click updates inspector, does not navigate). **Trust panel** renders the per-query guardrail log. Abstain banner on silencio. Calidad L1 accordion **starts collapsed** and reads static `evals/l1.json`. If that file is the shipped fixture, the expanded section labels numbers unpublished/sample. Clear button + typed `/clear`. `State` holds `session_id`.

`GET /health` returns `last_refresh`, `to_as_of`, `last_comm_id`, `n_docs`, `index_ready` (HTTP **200** when empty; fields present, null/`0` allowed; not 503). SHOULD also return the embedding model name.

Compose: API service on the existing ingest image/volume; **command override** (image `CMD` stays ingest). Jobs stay behind the jobs profile. Default `up` starts the API. README `## How to run` lists the API/`compose up`/`evals/run_l1.py` commands.

### Decision: Settings defaults

OpenAI-compatible `LLM_*` and `EMBEDDING_*`. Also: `DEMO_API_KEY` optional; max message **4000** chars; default k **5**, max k **8**; rate **20** chat requests / **60s** / client (HTTP 429 or delay); structlog `request_id`. Extra env keys stay ignored.

### Decision: IBM 1–4 take/leave

| Take | Leave |
|---|---|
| Prompt template with last_refresh / to_as_of; structured JSON; FastAPI not Flask | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters; upsert on refresh | Recommender |
| Vector search; parent doc = get_section; self-query ≈ regex+filters; HNSW default | FAISS second index; multi-query unless L1 citation-id is poor |

### Decision: Evals vs guardrails

Guardrails: per-query log (pass / warn / block) shown in the UI trust panel next to the answer; Gherkin; sidecar (scores, not RAGAS). `warn` is used when freeze honesty rewrites unqualified “vigente hoy”; other v1 rules pass or block. L1: `evals/gold.jsonl` + `run_l1.py` → `evals/l1.json`; commit a **fixture** `evals/l1.json` labeled unpublished/sample so the accordion is not empty before an operator run. UI accordion starts **collapsed** and reads that file. CI does not pay for L1. RAGAS is an **optional extra** for the operator command; default pytest and the demo image MUST NOT require it.

### Decision: Slip order

1. Deontic retry (not a v1 spec MUST) 2. Streaming 3. Chunking B on A-series (keep B on TO) 4. Gold cap 30 5. Coverage gate is src >= 80%. Filter integrity is specified: if filters are sent, honor them. Never cut: TO + post-TO ingest, resume+refresh CLI, last_refresh banner, cite-or-abstain, citation-id, unit tests, uv/ruff/mypy/pytest --cov, health HTTP 200 on empty index, polite download.

## Risks / Trade-offs

- [TO stale vs catalog] → vigente search TO ∪ A’s after the fecha (or number) of `to_as_of` (A 8359 class).
- [Truncating all A’s] → only reprint packs become events.
- [40-year superseded tail] → named lookup + superseded gold + vigente router.
- [1990–97 hole] → document; do not crawl.
- [Header pollution] → strip running TO headers or B wins for the wrong reason.
- [Legal] → unofficial extract on every answer + banner.
- [Hexagon bloat] → five ports max.
- [Memory invents law] → retrieve every follow-up; test `/clear`.
- [Silent cron] → health `last_refresh` age.
- [BCRA IP block] → politeness + resume.
- [Empty volume] → `index_ready=false` + HTTP 200 + chat silencio without LLM.
- [Public LLM bill] → queue + rate limit + optional `DEMO_API_KEY`.
- [GHA cannot hold index] → host crontab/compose only.
- [Incidental xref over-silencio] → silencio only when the asked-for rule lives only in the missing target.
- [Missing `fecha` after index repair] → copy MANIFEST fecha on repair.
- [Fixture L1 looks real] → unpublished/sample label in UI and README.
- [Multi-worker splits sessions] → one replica, one worker.

## Migration Plan

Ingest is already applied. This change adds the API+Gradio process on the same volume. Operator runs `jobs.ingest` before demo if the volume is empty. Rollback: delete volume and image; no user data.

## Open Questions

Recorded (behavior is decided in specs/design above; these are implementer notes, not open product forks):

- Back-matter skip is query-time heading/body, not ingest `doc_part`.
- LangGraph is not in v1; AnswerQuery is a Python function graph.
- tipo `A` = Comunicación A (`comunicacion` + reprint `event`); TO is not tipo `A`.
- Citation id = dump document id (`A8359` / `texto_ordenado`).
- Session memory is single-worker; Redis is later.
- Embedding vs chat provider keys remain Settings values, not behavior.
