## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Three operator-facing gaps remain. `prepare_turn` (`src/bcra_rag/api/handle.py:53-60`) consumes the daily turn cap before the per-client burst limiter and before any guardrail, so a scope-blocked weather question or a turn refused by the IP limiter still costs one of the 30 daily turns of a mailbox. When `CHAT_TURN_EVALS` is on, the two judge calls run inline before the response is returned (`use_cases/answer_query.py:105-108`), adding their latency to every answer. `evals/run_l1.py` publishes numbers but nothing compares them to a floor, so a retrieval or prompt regression only shows up when someone reads `evals/l1.json`.

## What Changes

- The per-client burst limiter SHALL be checked before the daily caps, and a counted turn whose input guardrails block it SHALL be refunded to both caps. (MODIFIED `platform` "Daily language-model turn caps".)
- Per-turn judge scoring SHALL run as a background task after the response is returned, keeping the `chat.turn` span open until scoring finishes and still logging `chat_turn_eval`.
- L1 SHALL support a threshold gate: `evals/gate.toml` holds per-metric floors; `evals/run_l1.py --gate [path]` exits non-zero and prints each failing metric; a skipped suite fails the gate unless `--gate-allow-skipped`. The new command is listed in `scripts/commands.toml`, README and AGENTS.md.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `platform`: cap ordering and refund; background judge.
- `evals-l1`: threshold gate command.
- `query-logging`: `chat_turn_eval` after the response.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Persisting turn caps across restarts (would add a sixth port); per-process memory stays.
- Expanding the gold set (domain authoring); only the gate mechanism ships.
- Running the paid L1 gate in CI.

## Impact

- `src/bcra_rag/api/turn_caps.py` (`release`), `src/bcra_rag/api/handle.py` (order, refund), `src/bcra_rag/api/routes.py` (pass `turn_caps`), `src/bcra_rag/use_cases/answer_query.py` (`run` background scoring, `drain_turn_evals`), new `src/bcra_rag/evals/domain/gate.py`, `evals/gate.toml`, `evals/run_l1.py`, `scripts/commands.toml`, README, AGENTS.md, `deploy/env.remote.example` (settings from changes 04/06/08 if not already listed).
- Tests: `tests/test_chat_api.py`, `tests/test_answer_query.py`, new `tests/evals/test_gate.py`, `tests/test_devtui.py::test_check_real_readme` (command sync).
