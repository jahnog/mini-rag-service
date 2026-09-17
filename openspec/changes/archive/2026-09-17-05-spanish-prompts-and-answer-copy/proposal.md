## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The model is asked in English to answer in Spanish: `SYSTEM_PROMPT` (`src/bcra_rag/adapters/llm_openai.py:34-43`) and the twelve-line reminder in `_prompt` (`src/bcra_rag/use_cases/answer_query.py:661-694`) are English, so the local model reasons in English ("Here's a thinking process: 1. Analyze User Input…") and translates, which costs time and hurts `finding_exact` (0.17 in `evals/l1.json`) because the six finding labels are never defined. Internal identifiers leak into what the user reads: every non-model answer ends with `last_refresh=2026-09-10T02:35:28+00:00; to_as_of=A8307.` (`_finalize`, `:394-397`), the prompt orders "Name last_refresh and to_as_of in the answer", `FreezeHonestyRail` appends `(last_refresh=…; to_as_of=…)` (`domain/guardrails/output.py:99-108`), and a blocked turn says `No puedo responder (injection).` with the raw rule id (`:190,:217,:493`).

## What Changes

- The system prompt SHALL be Spanish, SHALL define each `finding` label in one line, SHALL carry the citation and abstain rules that today live in the per-turn reminder, and SHALL include two short JSON examples (one cited, one silencio). The per-turn prompt keeps the DATA-ONLY framing, the random delimiter and the `[chunk_id=<doc_id> punto=<punto>] <text>` line format.
- The prompt-leak rail SHALL fingerprint the new Spanish prompt as well as the legacy English sentences.
- Freeze information SHALL be shown as a Spanish footer sentence — "Según el dump del <fecha> (texto ordenado al <to_as_of>)." — instead of `last_refresh=…; to_as_of=…`; the freeze-honesty rail SHALL accept either the ISO value or its date prefix. (MODIFIED `guardrails` "Freeze honesty".)
- Blocked answers SHALL use human Spanish copy per rule ("No puedo responder: …") instead of the rule id.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `query-answering`: Spanish prompt with finding definitions; Spanish freeze footer; human block copy.
- `guardrails`: freeze honesty accepts the footer; prompt-leak fingerprints the Spanish prompt.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Changing the JSON contract keys (`answer`, `finding`, `citations`), the `Fuente:` line, or the citation `snippet` verbatim rule (change 06 relaxes it).
- Re-running L1 (operator step after this change; expect `finding_exact` and latency to move).

## Impact

- `src/bcra_rag/adapters/llm_openai.py` (`SYSTEM_PROMPT`), `src/bcra_rag/use_cases/answer_query.py` (`_prompt`, `_finalize`, block copy, `Fuente` logic untouched), new `src/bcra_rag/domain/freeze.py` and `src/bcra_rag/domain/guardrails/copy.py`, `src/bcra_rag/domain/guardrails/output.py` (`PROMPT_FINGERPRINTS`, `FreezeHonestyRail`), `src/bcra_rag/ui/config.py` (`dump_date` re-export).
- Tests: `tests/test_llm_port.py`, `tests/test_guardrails.py`, `tests/test_answer_query.py`, `tests/features/test_chat_bdd.py` + `chat.feature`, `tests/fixtures/guardrail_probes.jsonl`, `tests/chat_fixtures.py` (`IN_CORPUS_DRAFT` answer), `tests/test_ui.py:421,782,862` literals.
- No command change; README Evals notes the operator rerun.
