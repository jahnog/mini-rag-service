## Context

See proposal.md Why and `specs/query-answering/spec.md` for the chat contract.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session, one worker, `/clear`. Router and session untouched.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions).

Constraints: Python 3.11+ via uv; pydantic v2 `LlmDraft` with `citations: list[Citation]` and `Citation.tipo` required; `LlmAdapter.complete` currently `model_validate_json`s the completions body. Live xAI JSON observed: `citations` is the string `Fuente: texto_ordenado`. `AnswerQuery` already builds public citations from dump hits and overlays model citations only when the id is in the dump; that merge never runs if `complete()` raises. `UnavailableLlm` still raises; `test_llm_failure_is_silencio_not_exception_text` is the failed-call contract.

## Goals / Non-Goals

**Goals:**

- Coerce messy completions JSON into `LlmDraft` at the Llm adapter so `complete()` returns a draft instead of raising on citation shape.
- Keep `AnswerQuery` control flow: hits → `_citations_from_hits` → overlay. Prompt text only.
- Unit tests with no live xAI. `src` coverage >= 80%.

**Non-Goals (design-level):**

- New port, domain hexagon type, or JSON-schema `response_format`.
- Changing router, Chroma, ingest, Gradio, or default `LLM_MODEL`.
- Salvaging non-JSON bodies into a draft (those MAY still raise → `llm_unavailable`).

## Decisions

### Decision: Parse at the Llm adapter, not in AnswerQuery

Add a pure function `parse_llm_draft(raw: str) -> LlmDraft` in `src/bcra_rag/adapters/llm_openai.py`. `LlmAdapter.complete` calls it on `message.content` instead of `LlmDraft.model_validate_json(raw)` alone.

Coercion:

| Incoming `citations` | Result |
|---|---|
| missing / null | `[]` |
| string | extract dump ids (`texto_ordenado`, `A` + 3–5 digits); each becomes a citation object |
| list of strings | same id extract per string |
| list of objects | keep `id` if dump-shaped; infer `tipo` (`texto_ordenado` → `TO`, else `A`) when omitted; drop entries without an id |
| other | `[]` |

Invalid or missing `finding` → `silencio`. Missing `answer` still fails validation (call failure path). Dump-shaped id means `texto_ordenado` or `A` + digits, matching existing citation ids.

`LlmPort.complete` still returns `LlmDraft` or raises. `AnswerQuery`’s `except Exception` → `llm_unavailable` stays for transport, missing key, and unparseable non-JSON.

Alternatives: coerce inside `AnswerQuery` (leaks JSON repair into the use case); a new domain module (YAGNI); `json_schema` response format (xAI `json_object` is what we have; coercion is the defense).

### Decision: Hits already fill empty model citations

Do not change the merge in `AnswerQuery`. After a successful `complete()`, `_citations_from_hits` is the source of public citations; model citations overlay only matching dump ids. Empty coerced `citations` therefore still show dump hits. Named Com. A and vigente share that path.

Tighten system text in `LlmAdapter` and `_prompt` in `answer_query.py`: `citations` is an array of objects `{id, tipo, punto, snippet}`; `Fuente:` belongs in `answer`. Keep `response_format={"type": "json_object"}`.

### Decision: Tests stub the client; no live API

- Parser unit tests in `tests/test_llm_port.py` (string, list of strings, missing `tipo`, invalid finding, empty/unusable citations).
- `LlmAdapter.complete` with a stub OpenAI client returning messy JSON (same file).
- Keep `test_llm_failure_is_silencio_not_exception_text`.
- Add `AnswerQuery` test: `FakeLlm` draft with empty `citations` still returns dump citation objects (documents the merge).

No paid completions in CI.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| 1 Ground in dump ids + `last_refresh` / `to_as_of` | Multi-agent / HITL |
| 2 Cite or abstain | LlamaIndex / second index |
| 3 Deterministic finding demotion after generation | Deontic scan as v1 MUST |
| 4 Visible guardrail log | Filling 1990–97 hole |

Slip order (design only): citation honesty → freeze dates → deontic scan later. Deontic scan stays slip-first, not this change.

## Risks / Trade-offs

- [Model still writes `citations` as a string] → Coerce ids; hits fill the rest. Prompt is hygiene, not the only defense.
- [Coercion picks a wrong id from a long string] → Overlay only dump ids already in hits; unknown ids are dropped.
- [Non-JSON body] → Still `llm_unavailable`. Honest silencio beats inventing clauses.
- [Stashed `LLM_MODEL=grok-4.3` WIP] → Out of this change; xAI already aliases `grok-4-1-fast`.

## Migration Plan

Deploy the serving process (one worker) as today. No dump wipe, no index rebuild, no env key change. Rollback: previous adapter `model_validate_json` only (chat would abstain on messy JSON again).
