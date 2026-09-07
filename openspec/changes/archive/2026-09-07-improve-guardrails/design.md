## Context

See proposal.md Why. Product runtime already exists: five ports (Catalog, Extractor, Index, Llm, SessionStore), composition root `build_app` / `build_ingest`, ingest/refresh on the dump host, Router (named Com. A / vigente / similarity, chunker B on TO + clean A’s), in-process session, Gradio on FastAPI, v1 regex rails in `domain/guardrails.py`, structlog `chat_turn` to `DATA_DIR/logs/chat.log`.

## Goals / Non-Goals

**Goals:**

- One `GuardrailPipeline` with stages input / retrieve / output; generate is the LLM, logged as a step.
- Policy YAML as enable/enforce/backend; Settings keep caps.
- Staff log is `ChatResponse.guardrails`; Usuario hides the panel.
- Optional OTel to a sibling `uvx` Phoenix process; fail-open.

**Non-Goals:**

- Sixth port, DI container, classifier weights, completion-token cap, container images, ingest-time poison job in this change.

## Decisions

### Decision: one pipeline, retrieve is a stage

`GuardrailPipeline.run_stage(stage, ctx)` runs enabled Strategies in policy order. Retrieve-stage rails that inspect hits subclass `ChunkMappingRail` (loop + one summary chip). Alternatives: two pipeline classes (ceremony; AnswerQuery still calls them in order).

### Decision: composition registry, not import magic

`RAIL_BUILDERS` in `composition.py`. `build_app` builds the pipeline **once** on `ChatApp`. `TracedRail` Decorator; `NoOpTracer` when collector unset. Five ports unchanged.

### Decision: input order (raw vs compose)

Length on `ctx.raw` → normalize → AnswerQuery composes follow-up → remaining input rails on composed text. YAML lists length then normalize.

### Decision: honest short-circuit

Input `block` skips retrieve/generate. Output rails that only need the visible refusal still run. `cite-or-abstain` on silencio is `pass`. Shadow: `pass` + `would_block=true`, never `warn`.

### Decision: cite this-turn + quote

Citation id must be in this turn’s surviving dump ids; quote is whitespace-normalized substring of that hit (or the hit’s own truncated snippet if the model omitted a quote).

### Decision: InjectionBackend

Regex now; same backend on query and chunks. Future classifier is one extra + YAML `backend`. Regex has no threshold.

### Decision: HTTP vs logs

`GuardrailVerdict`: rule, verdict (`pass|warn|block|redact|skipped`), detail, stage, enforced, would_block. Latency and per-chunk metrics only on `chat_turn` and spans.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Structured JSON; FastAPI; prompt with last_refresh / to_as_of | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters | Recommender |
| Vector search; parent = get_section | Second index |

### Decision: Slip order

Never cut: staged log, this-turn cite, retrieve scan, unit tests, coverage >= 80%, fail-open collector.

Slip-first: Phoenix evals script, systemd Phoenix unit if the extra is unused, deontic scan.

## Risks / Trade-offs

- [This-turn citations vs L1] → intended; citation-id may move.
- [Quote substring too strict] → fall back to hit snippet when model quote empty.
- [Injection vs innocent “ignore”] → strong patterns only; gold answerable rows as benign set.
- [Live tree forbids a certain container substring] → README/units say sibling `uvx` process.

## Migration Plan

No dump rebuild. Next API start loads packaged policy. Rollback: revert the change. Optional collector: unset endpoint, stop the sibling unit.

## Open Questions

None.
