## Context

See proposal.md Why. Five ports stay five; the evals vertical stays out of the chat process except for reading the static JSON.

Facts as of this change's writing:
- `NdcgAtK.score` (`code.py:81-89`): `rel = [1.0 if item in gold else 0.0 for item in top]`; `ideal = [1.0] * min(self._k, len(set(gold)))`. With `retrieved_ids` being chunk-level ids that repeat a doc id, `dcg > idcg`.
- `ui/config.py:136-149 load_l1`, `:152 is_sample_l1`, `:156-192 l1_markdown`, `:201-211 _suite_markdown` (dumps `key: value` verbatim, skipping `skipped`/`skip_reason`). Suite dicts carry `n`, `latency_ms_p50`, `latency_ms_p95`, `n_context_recall`, `context_source`. Top-level `judge` = `{model, skipped, skip_reason, calls, tokens_in, tokens_out}`.
- `gradio_app.py:378-379` reads `Path(settings.evals_dir) / "l1.json"` once in `build_blocks`.
- `scripts/deploy.sh:74-90`: rsync excludes `evals/l1.json`; seeds only when dest missing AND local is unpublished/sample. `tests/test_deploy.py:196-205` asserts the comment words and ordering.
- `api/routes.py:72-74` `GET /health` pattern; `settings.evals_dir` available as `api.state.settings`.
- `tests/prod/test_smoke.py` uses `make_client()` + `raise_for_limiter`; `CONTRACT_KEYS`/`HEALTH_KEYS` style.
- README lines ~154-158 and `openspec/specs/evals-l1/spec.md:147-218`.

## Goals / Non-Goals

**Goals:** correct metric; readable accordion; the published document reaches new hosts; an operator can `curl /l1`.
**Non-Goals:** live refresh of the accordion; touching gold or run flags.

## Decisions

### Decision: NDCG credits each gold id once

```python
seen: set[str] = set()
rel: list[float] = []
for item in top:
    hit = item in gold and item not in seen
    if hit:
        seen.add(item)
    rel.append(1.0 if hit else 0.0)
```
IDCG unchanged. Alternative: dedupe `retrieved_ids` before scoring — rejected (would also change hit/precision semantics silently).

### Decision: Rendering helpers, not a new schema

```python
_LATENCY_KEYS = ("latency_ms_p50", "latency_ms_p95")

def _fmt_metric(key: str, value: object) -> str:
    if value is None:
        return "omitido"
    if key in _LATENCY_KEYS and isinstance(value, (int, float)):
        return f"{int(round(value))} ms"
    if isinstance(value, bool):
        return "sí" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)
```
`_suite_markdown` heading becomes `## {title} (n={n})` when `n` is present, skips `n` in the body, and formats every value with `_fmt_metric`. `l1_markdown` adds after the generation block:
`Juez: {model} · omitido ({skip_reason})` when `judge.skipped` else `Juez: {model} · {calls} llamadas`. Missing `judge` → line omitted.

### Decision: `load_l1` moves to the domain, not the evals vertical

`tests/evals/test_isolation.py` requires chat sources never to import `bcra_rag.evals`, and `ui/config.py` imports Gradio, which the API must not depend on. Move `load_l1` and `is_sample_l1` to a new stdlib-only module `src/bcra_rag/domain/l1_results.py` and re-export both from `ui/config.py` (and keep the `bcra_rag.ui` package export) so existing imports keep working. `api/routes.py` imports from `bcra_rag.domain.l1_results`.

### Decision: `GET /l1` (not under `/evals`)

The `evals` capability spec states "There SHALL NOT be an HTTP evaluation endpoint" and `tests/evals/test_isolation.py::test_no_http_eval_route` rejects any route under `/evals`. The results document is not an evaluation (nothing runs; it is a static read), so it is served at `/l1`, outside that prefix, and the isolation rule stays untouched.

```python
@api.get("/l1")
def evals_l1() -> dict[str, Any]:
    return load_l1(Path(settings.evals_dir) / "l1.json")
```
Always 200: a missing file returns the same stub the UI uses (`unpublished: true, sample: true`). No auth (it is the same data every staff user sees; contains no secrets). Excluded from the OpenAPI schema? No — keep it documented (`include_in_schema` default).

### Decision: Deploy seeds the committed document when the host has none

Replace the seed block with:
```bash
# Seed dest evals/l1.json only when the host has none. The seed is the document
# committed at evals/l1.json in HEAD (the last operator run on the published dump,
# see README Evals) — never an uncommitted laptop run. An existing host document,
# unpublished, sample or operator run, is never overwritten.
if ! remote "test -f '$DEPLOY_DIR/evals/l1.json'"; then
  _seed_l1="$(mktemp)"
  if git -C "$REPO_ROOT" show HEAD:evals/l1.json > "$_seed_l1" 2>/dev/null; then
    rsync -a "$_seed_l1" "${DEPLOY_HOST}:${DEPLOY_DIR}/evals/l1.json"
  fi
  rm -f "$_seed_l1"
fi
```
The words "unpublished" and "sample" stay in the comment (existing tests search for them); the `python3 -c` published check is removed. `tests/test_deploy.py:204` currently asserts `"git show HEAD:evals/l1.json" not in text` — that assertion is inverted by this change (the committed document is exactly what must be seeded). Rationale: `scripts/publish-data.sh` publishes dump and results together, so the committed document describes the dump a fresh host installs, while a working-tree file may be a local run against another index.

### Decision: Spec and README wording

`evals-l1` "Static results file": the committed document MAY be a published operator run on the published dump and MUST carry `unpublished:false, sample:false` only when it is one; the UI labels by the file's flags. "Host install preserves operator L1": first install SHALL seed the committed document when none exists; updates MUST NOT overwrite. README Evals: replace "Shipped `evals/l1.json` stays unpublished/sample until an operator run on a ready index." with "Committed `evals/l1.json` is the last operator run on the published dump (published with `scripts/publish-data.sh`); a fresh host is seeded with it and keeps its own later runs." Add: "`ndcg_at_5` in the committed file predates the NDCG bound fix and can exceed 1 until the next operator run." Add `GET /l1` to the Debug paragraph.

## Risks / Trade-offs

- [Seeding a laptop run onto a host with a different dump] → mitigated by the wording: the committed file is only updated by `publish-data.sh` together with the dump.
- [`/l1` leaks the judge model name] → it is already visible in the staff UI.

## Migration Plan

Deploy normally; the next deploy to a host lacking `evals/l1.json` seeds it. Rollback: revert.

## Open Questions

None.
