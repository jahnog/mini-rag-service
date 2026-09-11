## 1. query-answering — named-fetch salvage

- [x] 1.1 Thread `retrieval_route`, `named_id`, and `section_chars` from `Router.route` onto `RailContext`. In `AnswerQuery` / `generate_from_context`, snapshot model citations before empty-snippet fill; when route is `named`, named id is in `turn_ids`, and draft finding is not silencio: replace a bad/empty snippet for that id (`replaced_snippet`); if citations are empty and the answer names the dump id, attach a verbatim slice (`attached_named`); otherwise leave the rail to block. Do not salvage vigente/similar. Verify `uv run pytest tests/test_answer_query.py -q`: paraphrased named A 3500 cites `A3500`; empty citations with `A3500` in the answer cite; empty citations without the id stay `cite-or-abstain`; similar-route paraphrase stays `cite-or-abstain`. Retarget `test_named_a3500_paraphrased_snippet_is_silencio`.

## 2. query-logging — chat_turn fields, tracer start, traces file

- [x] 2.1 Add `retrieval_route`, `named_id`, `section_chars`, `draft_finding`, `draft_citation_ids`, `cite_failures`, and `salvage` to the `chat_turn` record (model snippets before fill). Omit cite-failure fields on weather/scope and `/clear`. Still strip `thinking`, prompt, secrets. Verify `uv run pytest tests/test_logconfig.py tests/test_answer_query.py -q`: named paraphrase logs `quote_not_in_hit` and `named_id=A3500`; weather has no cite-failure fields.

- [x] 2.2 Wrap the inner tracer in `build_tracer` with a file writer to `DATA_DIR/logs/traces.jsonl` (`name`, `layer`, `t`, truncated `input.value`, `retrieval.route`, `sink=local`, `otel=enabled|disabled`). Fail-open on write (`trace_file_failed`). Log `tracer_disabled` (`endpoint_unset` / `otel_extra_missing` / `register_failed`) or `tracer_enabled` (host + project, no key) once at start. Verify `uv run pytest tests/evals/test_tracer.py tests/test_composition.py tests/test_answer_query.py -q`: NoOp + tmp DATA_DIR writes `chat.turn` and `retrieve` for named A 3500; weather writes `scope` not `retrieve`; unwritable path still answers; `tracer_disabled` reason `endpoint_unset` when collector empty.

## 3. platform — smoke timeout status

- [x] 3.1 Record last collector HTTP status (or connect error) in `list_spans` / `wait_for_turn_with_child` and include it in `PhoenixTimeout`. Still fail closed; do not skip cite-or-abstain. Verify `uv run pytest tests/test_prod_phoenix.py -q`: 401 timeout names 401; empty 200 still says dump host is not exporting.

## 4. retrieval / notes

- [x] 4.1 README `## How to run` Debug: one clause that compact per-span records go to `data/logs/traces.jsonl` (or `DATA_DIR/logs/traces.jsonl`) whether or not the collector is set, and that write failures do not fail chat. No new command fence. Verify `uv run pytest tests/test_notes.py -q` after extending operator bullets if that test names chat.log / Phoenix.

- [x] 4.2 Run `uv run ruff check .`, `uv run mypy src`, then `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml`. Fix until green with src coverage >= 80%. Do not run a paid L1 eval. Do not run `--run-prod-smoke` as a CI-blocking task.
