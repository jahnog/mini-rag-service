## Context

See proposal.md Why. Five ports stay five.

Facts as of this change's writing:
- `TurnCaps` (`api/turn_caps.py:8-34`): `allow(email) -> str | None` increments `_email_day[(email, day)]` and `_process_day[day]` when under both caps; returns `"email_cap"`/`"process_cap"` otherwise. Tests `tests/test_chat_api.py:268-390`.
- `prepare_turn` (`api/handle.py:35-68`): auth → demo key → `turn_caps.allow` (unless `/clear`) → `limiter.allow(client_id)` → k cap. `run_prepared_turn(prepared, *, settings, index, llm, sessions, pipeline, message, k, filters, request_id, on_thinking, turn_evaluator, thinking, on_phase)` builds `AnswerQuery` and runs it; `handle_turn` calls both; `routes.py:76-108` calls `prepare_turn` then wraps `run_prepared_turn` in `json_chat_chunks`.
- `ChatResponse.guardrails` items have `rule`, `stage`, `verdict`, `enforced`.
- `AnswerQuery.run` (`answer_query.py:82-128`): opens the `chat.turn` span, `_respond`, `scores = await self._score_turn(...)`, `record_scores`, `_bind_turn_span`, logs `chat_turn_eval`, `finally` exits the span. `_score_turn` returns `TurnScores()` when the generate step did not pass. Tests: `tests/test_answer_query.py:1103-1160` (`_FakeTurnEvaluator`, `RecordingTracer.spans["chat.turn"].attrs`).
- `evals/run_l1.py::main` builds settings/app, `asyncio.run(run_l1(...))`, no exit code; `_parse()` argparse. `run_l1` writes `evals/l1.json` via `to_payload` (`evals/use_cases/run_l1.py:238-280`); published keys include `retrieval.{hit_at_5, precision_at_5, mrr, ndcg_at_5, skipped}`, `generation.{citation_id_exact, citation_punto_exact, citation_snippet_grounded, finding_exact, skipped}`, `slices`.
- Commands: `scripts/commands.toml` entries `l1`, `l1-deterministic`, `l1-retrieval`, `l1-generation`, `l1-host` (group Evals, block `evals`); README fence `<!-- commands:evals -->` (line ~166); AGENTS.md table rows 36-40; `tests/test_devtui.py::test_check_real_readme` runs `scripts/devtui.py --check`.
- PyYAML is not a direct dependency; `tomllib` is stdlib.

## Goals / Non-Goals

**Goals:** fair caps; judge latency off the critical path; a mechanical regression check for L1.
**Non-Goals:** SQLite caps; gold expansion; CI gate.

## Decisions

### Decision: Limiter first, caps second, refund on input block

`prepare_turn` order: auth → demo key → `limiter.allow(client_id)` (429) → `turn_caps.allow(email)` (429, logged) → k cap. `TurnCaps.release(email)` decrements both counters for today when above zero. `run_prepared_turn(..., turn_caps: TurnCaps | None = None)`: after `use_case.run` returns, if `turn_caps is not None` and `message.strip().lower() != "/clear"` and `any(g.stage == "input" and g.verdict == "block" and g.enforced for g in response.guardrails)`: `turn_caps.release(prepared.email)` and log `chat_cap_refund` with the email hash prefix. `handle_turn` and `routes.py` pass `turn_caps=`. Spec: "A counted question blocked by an input guardrail SHALL be refunded".

### Decision: Background judge, span kept open

```python
_BACKGROUND: set[asyncio.Task[None]] = set()

async def drain_turn_evals() -> None:
    if _BACKGROUND:
        await asyncio.gather(*list(_BACKGROUND), return_exceptions=True)
```
`run()`: open span; `response = await self._respond(...)`; decide `llm_called` (same predicate as `_score_turn`); if the evaluator is `NoOpTurnEvaluator` or not `llm_called`: bind span attributes, exit the span, return (synchronous path, as today minus scores). Otherwise: bind the span with empty scores, then `task = asyncio.create_task(self._score_and_close(request, response, span, span_cm, setter))`, add to `_BACKGROUND`, `task.add_done_callback(_BACKGROUND.discard)`, return `response`. `_score_and_close` awaits `_score_turn`, `record_scores`, re-runs `_bind_turn_span(setter, response, scores)`, logs `chat_turn_eval`, and exits the span in `finally`. Tests call `await drain_turn_evals()` before asserting span attributes.

### Decision: TOML gate

`evals/gate.toml`:
```toml
[thresholds]
hit_at_5 = 0.8
precision_at_5 = 0.7
mrr = 0.7
citation_id_exact = 0.2
citation_snippet_grounded = 0.25
finding_exact = 0.15
```
`src/bcra_rag/evals/domain/gate.py`:
```python
def load_thresholds(path: Path) -> dict[str, float]: ...        # tomllib, [thresholds] floats
def evaluate_gate(payload: Mapping[str, Any], thresholds: Mapping[str, float], *, allow_skipped: bool = False) -> list[str]:
    # for each metric: look in payload["retrieval"] then payload["generation"]; if the owning block is skipped → failure "generation skipped (missing_extra)" unless allow_skipped; if value is None or < floor → f"{name}: {value} < {floor}"
```
`evals/run_l1.py`: `--gate` (optional path, default `evals/gate.toml`, `nargs="?"`, `const=<default>`), `--gate-allow-skipped`; after `run_l1` returns, load `evals/l1.json`, `failures = evaluate_gate(...)`, print each as `GATE FAIL <line>` and `sys.exit(1)` when any; else print `GATE OK`. `commands.toml` entry `l1-gate` (`argv = ["uv", "run", "python", "evals/run_l1.py", "--gate"]`, summary "Run L1 and fail if any metric is under evals/gate.toml", `confirm = true`), README fence line `uv run python evals/run_l1.py --gate`, AGENTS.md row `| L1 gate | \`uv run python evals/run_l1.py --gate\` |`.

## Risks / Trade-offs

- [Refund makes an attacker's blocked spam free] → the burst limiter still applies per client; caps protect the paid model, which a blocked turn never reaches.
- [Background task outlives the request in tests] → `drain_turn_evals()`; the process exits normally because tasks are short.
- [Gate floors go stale after prompt/retrieval changes] → floors sit just under the published numbers; edit the TOML with the rerun.

## Migration Plan

Deploy normally. Update `evals/gate.toml` floors together with each `evals/l1.json` publish.

## Open Questions

None.
