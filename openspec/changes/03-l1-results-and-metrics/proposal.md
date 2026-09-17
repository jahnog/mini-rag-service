## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The Calidad L1 panel is populated from `evals/l1.json` (n=30, published) but the numbers it shows are partly wrong or unreadable, and the file does not reach a fresh host: `ndcg_at_5` is 1.647 because `NdcgAtK` (`src/bcra_rag/evals/domain/metrics/code.py:81-89`) credits every retrieved chunk that matches a gold document id while the ideal DCG is capped at the number of distinct gold ids; the accordion prints raw floats such as `latency_ms_p95: 137652.6405` and never shows `n` or that the judge was skipped (`missing_extra`); `scripts/deploy.sh:84-90` refuses to seed a published document and the committed file is published, so a new dump host shows the empty "Números de muestra" stub; README and the `evals-l1` spec still say the shipped file is an unpublished sample. There is also no read-only way to check which L1 document a running host serves.

## What Changes

- NDCG@k SHALL be bounded to [0, 1]: each gold document id gains at most once, at its first rank. The published `ndcg_at_5` stays as-is until the operator reruns L1 (documented).
- The L1 accordion SHALL render rounded numbers (rates to 3 decimals, latencies as integer milliseconds), the sample size `n` per suite, and a "Juez" line stating the judge model and whether it ran or was skipped with the reason.
- The committed `evals/l1.json` SHALL be the last operator run on the published dump; installing the application on a host with no results document SHALL seed it, and updating SHALL never overwrite a host's own results. (MODIFIED `evals-l1` "Static results file", "Host install preserves operator L1".)
- The serving process SHALL expose `GET /evals/l1` returning the stored results document (read-only), and the production smoke SHALL assert it is a published run.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `evals-l1`: NDCG bound; shipped results document semantics; host seeding; `GET /evals/l1`.
- `assistant-ui`: L1 accordion rendering (rounding, `n`, judge line).
- `prod-smoke`: L1 document is served and published.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Re-running L1 or regenerating `evals/l1.json` in this change (operator paid run).
- Refreshing the accordion without a process restart (the service restart in `deploy/l1.sh` remains the reload).
- Changing gold rows or adding metrics.

## Impact

- `src/bcra_rag/evals/domain/metrics/code.py`, `src/bcra_rag/ui/config.py` (`_suite_markdown`, `l1_markdown`, `load_l1`/`is_sample_l1` moved to `src/bcra_rag/domain/l1_results.py` and re-exported), `src/bcra_rag/api/routes.py` (`GET /evals/l1`), `scripts/deploy.sh`, `README.md` Evals section, `openspec/specs/evals-l1/spec.md`.
- Tests: `tests/evals/test_metrics.py`, `tests/test_ui.py`, `tests/test_chat_api.py`, `tests/test_deploy.py`, `tests/prod/test_smoke.py`.
- No new operator command (the endpoint is read-only); README `## How to run` unchanged except the Evals wording.
