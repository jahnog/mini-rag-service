## Context

See proposal.md Why and the delta specs under `specs/` for named-fetch salvage, chat-turn fields, and the local traces file.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container. `build_tracer` still fail-opens.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session (last six messages), one worker, `/clear`.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions). Production on the lab host is `bcra-mini-rag-production.service`, not `scripts/deploy.sh`.

Constraints: Python 3.11+ via uv; pydantic v2; FastAPI; Gradio on FastAPI; structlog JSON `chat.log`; optional `otel` extra; `src` coverage >= 80%.

## Goals / Non-Goals

**Goals:**

- Named-fetch salvage in `AnswerQuery` so paraphrased/empty snippets do not hide a successful A 3500 fetch when the model already named the dump id.
- Reconstructable `chat_turn` fields and a compact `DATA_DIR/logs/traces.jsonl` from the Tracer port we own.
- Tracer enabled/disabled log at `build_tracer`.
- Smoke `PhoenixTimeout` includes last collector HTTP status.

**Non-Goals (design-level):**

- Wrapping `phoenix.otel.register`’s exporter; product `flush()`; generate retry; `get_section` order; dump-host `--extra otel` install; changing `LLM_MODEL`.

## Decisions

### Decision: salvage in AnswerQuery, not CiteOrAbstainRail

The rail stays “this-turn dump id + verbatim snippet.” `_citations_from_model` already fills **empty** snippets from the hit for every route. Named salvage runs after that fill, only when `Router.kind == "named"` and `named_id` is in `turn_ids` and draft finding is not silencio:

1. If a citation id equals `named_id` and `_quote_ok` fails, replace `snippet` with `hit.text[:280]` (`replaced_snippet`).
2. Else if citations are empty and `_draft_names_id(answer, named_id)`, append that citation (`attached_named`).
3. Else leave citations as-is (`none`) and let the rail block.

Thread `retrieval_route`, `named_id`, `section_chars` on `RailContext` from `Router.route`. Do not attach a citation when the draft never names the id.

Alternatives: weaken the rail globally (rejected; vigente/similar stay strict); generate retry (paid, still flakes).

### Decision: cite_failures from model snippets before fill

Snapshot `draft.citations` **before** `_citations_from_model` empty-snippet fill. Classify each: `unknown_id` (id not in `turn_ids`), `empty_snippet`, `quote_not_in_hit`. Log those plus `draft_finding`, `draft_citation_ids`, `salvage` on `chat_turn`. Input blocks skip the fields.

### Decision: File-backed Tracer port, not OTLP exporter wrap

`build_tracer` always wraps the inner tracer (`_OtelTracer` or `NoOpTracer`) with a writer that on `span().__exit__` / `record_retriever` appends one JSON line to `settings.data_dir / "logs" / "traces.jsonl"`. Fields: `name`, `layer`, `t`, truncated `input.value`, `retrieval.route`, `sink=local`, `otel=enabled|disabled`, `reason` when disabled. Write errors → `trace_file_failed` structlog, chat continues.

At start: `tracer_disabled` (`endpoint_unset` / `otel_extra_missing` / `register_failed`) or `tracer_enabled` (project, collector host only). Distinguish missing extra via `ModuleNotFoundError` on `phoenix.otel`.

Alternatives: wrap OTLP exporter (cannot see register’s exporter; misses NoOp); write only on export failure (undetectable).

### Decision: smoke timeout names HTTP status

`list_spans` records last status (or `connect`). `PhoenixTimeout` includes it. Still fail closed. Do not skip cite-or-abstain. Do not fall back to `PHOENIX_PROJECT_NAME`.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Structured JSON; FastAPI; prompt with last_refresh / to_as_of | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters | Recommender |
| Vector search; parent = get_section | Second index |

### Decision: Slip order

Never cut: named-fetch salvage when the model names the id; cite-or-abstain on vigente/similar; local traces file fail-open; unit tests; coverage >= 80%.

Slip-first: deontic scan; `get_section` reading order; generate retry.

## Risks / Trade-offs

- [Salvage ships a grounded snippet with a still-paraphrased answer] → snippet is verbatim; answer was already model prose; similar route unchanged.
- [Attach-if-answer-names matches incidental “A 3500” in a wrong answer] → named route already fetched that id; still better than silencio on the smoke probe.
- [traces.jsonl grows] → ~1KB/turn; same posture as `chat.log`; rotation out of scope.
- [ProtectSystem=strict] → file is under `DATA_DIR/logs` already writable for `chat.log`.
- [Collector still empty until operator installs otel extra] → `tracer_disabled` + traces.jsonl make that greppable; smoke stays fail-closed.

## Migration Plan

No dump or index migration. Deploy is a normal API restart. Rollback is revert; cite-or-abstain on named paraphrase returns. Operators still must set dump-host `PHOENIX_*` and `--extra otel` for collector smoke; this change does not do that. README Debug names `data/logs/traces.jsonl`; no new command fence.

## Open Questions

None.
