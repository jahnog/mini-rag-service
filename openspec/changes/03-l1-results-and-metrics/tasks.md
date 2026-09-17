# Tasks — 03 L1 results and metrics

Requires change 01. Line anchors are as of this change's writing; grep the quoted symbol if they moved.

## 1. evals-l1 — NDCG bound

- [ ] 1.1 `src/bcra_rag/evals/domain/metrics/code.py::NdcgAtK.score` (~line 81-89): replace `rel = [1.0 if item in gold else 0.0 for item in top]` with
  ```python
  seen: set[str] = set()
  rel: list[float] = []
  for item in top:
      hit = item in gold and item not in seen
      if hit:
          seen.add(item)
      rel.append(1.0 if hit else 0.0)
  ```
  Keep `ideal`/`idcg` unchanged.
- [ ] 1.2 `tests/evals/test_metrics.py`: add (uses the existing `_gold(**kwargs)` and `_chunk(doc_id)` helpers and `NdcgAtK` from `bcra_rag.evals.domain.metrics` — add it to the import list if absent):
  ```python
  def test_ndcg_counts_each_gold_id_once() -> None:
      gold = _gold(gold_ids=["texto_ordenado"], gold_puntos=[])
      ids = ["texto_ordenado", "texto_ordenado", "A8359", "texto_ordenado", "A3500"]
      sample = RetrievalSample(gold=gold, hits=[_chunk(i) for i in ids], retrieved_ids=ids)
      assert NdcgAtK(5).score(sample).value == 1.0


  def test_ndcg_first_hit_rank_and_bound() -> None:
      import math

      gold = _gold(gold_ids=["A3500"], gold_puntos=[])
      ids = ["A8359", "A3500", "A3500", "A3500", "A3500"]
      sample = RetrievalSample(gold=gold, hits=[_chunk(i) for i in ids], retrieved_ids=ids)
      value = NdcgAtK(5).score(sample).value
      assert abs(value - 1 / math.log2(3)) < 1e-9
      assert 0.0 <= value <= 1.0
  ```
  Verify: `uv run pytest tests/evals/test_metrics.py -q` → passes.

## 2. domain — results loader module

- [ ] 2.1 Create `src/bcra_rag/domain/l1_results.py` containing `load_l1(path: Path) -> dict[str, Any]` and `is_sample_l1(data: dict[str, Any]) -> bool` moved verbatim from `src/bcra_rag/ui/config.py` (~lines 136-153; imports: `json`, `Path`, `Any`). Add `L1_FILENAME = "l1.json"`.
- [ ] 2.2 In `ui/config.py` delete the two functions and add `from bcra_rag.domain.l1_results import is_sample_l1, load_l1` (keep them in `__all__`/module namespace so `bcra_rag.ui.__init__` and `tests/test_ui.py:45-48` still import them from `bcra_rag.ui.config`). `gradio_app.py:378` may use `L1_FILENAME`. Verify: `uv run pytest tests/test_ui.py -k l1 -q` → passes; `uv run pytest tests/evals/test_isolation.py -q` → passes.

## 3. assistant-ui — accordion rendering

- [ ] 3.1 `ui/config.py`: above `_suite_markdown` add
  ```python
  _LATENCY_KEYS = frozenset({"latency_ms_p50", "latency_ms_p95"})


  def _fmt_metric(key: str, value: object) -> str:
      if value is None:
          return "omitido"
      if key in _LATENCY_KEYS and isinstance(value, int | float) and not isinstance(value, bool):
          return f"{int(round(value))} ms"
      if isinstance(value, bool):
          return "sí" if value else "no"
      if isinstance(value, float):
          return f"{value:.3f}"
      return str(value)
  ```
  Rewrite `_suite_markdown` (~line 201-211):
  ```python
  def _suite_markdown(title: str, block: dict[str, Any]) -> str:
      if not block:
          return f"## {title}\n\n(sin datos)"
      if block.get("skipped"):
          reason = block.get("skip_reason") or "omitido"
          return f"## {title}\n\nomitido ({reason})"
      n = block.get("n")
      heading = f"## {title} (n={n})" if n is not None else f"## {title}"
      lines = [heading, ""]
      skip = {"skipped", "skip_reason", "n"}
      for key, value in block.items():
          if key in skip:
              continue
          lines.append(f"- {key}: {_fmt_metric(key, value)}")
      return "\n".join(lines)
  ```
  In `l1_markdown` (~line 156-192) add after `generation_block = …`:
  ```python
  judge_line = _judge_markdown(data.get("judge"))
  ```
  and a helper
  ```python
  def _judge_markdown(raw: object) -> str:
      if not isinstance(raw, dict):
          return ""
      model = str(raw.get("model") or "—")
      if raw.get("skipped"):
          return f"Juez: {model} · omitido ({raw.get('skip_reason') or 'omitido'})"
      return f"Juez: {model} · {int(raw.get('calls') or 0)} llamadas"
  ```
  and insert `f"{judge_line}\n\n"` right after `f"{generation_block}\n\n"` in the returned f-string (when `judge_line` is empty this yields a blank line; acceptable — or guard with `(judge_line + "\n\n") if judge_line else ""`). Also format the headline numbers: `_skipped_or_value` returns `f"{value:.3f}"` for floats.
- [ ] 3.2 `tests/test_ui.py::test_l1_fixture_renders_operator_run` (~line 718): append
  ```python
  assert "## Generación (n=30)" in text
  assert "latency_ms_p95: 137653 ms" in text
  assert "137652.6405" not in text
  assert "Juez: grok-4.3 · omitido (missing_extra)" in text
  assert "citation_id_exact**: 0.233" in text
  ```
  and add
  ```python
  def test_l1_markdown_judge_ran_line() -> None:
      text = l1_markdown({"judge": {"model": "m", "skipped": False, "calls": 12}})
      assert "Juez: m · 12 llamadas" in text
  ```
  Verify: `uv run pytest tests/test_ui.py -k l1 -q` → passes.

## 4. evals-l1 — `GET /evals/l1`

- [ ] 4.1 `src/bcra_rag/api/routes.py`: import `from pathlib import Path` and `from bcra_rag.domain.l1_results import L1_FILENAME, load_l1`; after the `/health` route (~line 72-74) add
  ```python
  @api.get("/evals/l1")
  def evals_l1() -> dict[str, Any]:
      return load_l1(Path(settings.evals_dir) / L1_FILENAME)
  ```
- [ ] 4.2 `tests/test_chat_api.py`: add
  ```python
  def test_evals_l1_served(tmp_path: Path) -> None:
      client, _, _, _ = make_client(tmp_path, authenticate=False)
      body = client.get("/evals/l1").json()
      assert body["unpublished"] is False
      for key in ("retrieval", "generation", "judge", "n"):
          assert key in body


  def test_evals_l1_missing_returns_stub(tmp_path: Path) -> None:
      settings = Settings(data_dir=tmp_path, evals_dir=tmp_path / "no-evals")
      client, _, _, _ = make_client(tmp_path, settings=settings, authenticate=False)
      response = client.get("/evals/l1")
      assert response.status_code == 200
      assert response.json()["unpublished"] is True
  ```
  (`make_client` runs from the repo root, so the default `evals_dir` resolves to the committed file; import `Settings` from `bcra_rag.settings` if not already.) Verify: `uv run pytest tests/test_chat_api.py -k evals_l1 -q` → passes.

## 5. prod-smoke — L1 assertion

- [ ] 5.1 `tests/prod/test_smoke.py`: add next to `test_health_is_ready`
  ```python
  L1_KEYS = ("retrieval", "generation", "judge", "n")


  def test_l1_document_is_served(prod_health: dict[str, Any]) -> None:
      del prod_health
      client = make_client()
      try:
          response = client.get("/evals/l1")
          raise_for_limiter(response, what="GET /evals/l1")
          assert response.status_code == 200, f"GET /evals/l1 returned {response.status_code}"
          body = response.json()
          missing = [key for key in L1_KEYS if key not in body]
          assert not missing, f"GET /evals/l1 missing {missing}"
          assert not body.get("unpublished") and not body.get("sample"), (
              "host serves the unpublished stub; run L1 on the dump host"
          )
      finally:
          client.close()
  ```
  Verify: `uv run pytest tests/prod/test_smoke.py --collect-only -q` → the new test is collected (it only runs under `--run-prod-smoke`).

## 6. evals-l1 — deploy seeding, README, spec sync

- [ ] 6.1 `scripts/deploy.sh` (~line 84-90): replace the seed block with
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
- [ ] 6.2 `tests/test_deploy.py::test_deploy_seeds_unpublished_l1_json_only_when_dest_missing` (~line 196): rename to `test_deploy_seeds_committed_l1_json_only_when_dest_missing`; keep `exclude_idx < seed_idx`, `test -f`, `--delete-excluded` and `--ignore-existing` assertions; replace `assert "git show HEAD:evals/l1.json" not in text` with `assert "git -C \"$REPO_ROOT\" show HEAD:evals/l1.json" in text`; add `assert "python3 -c" not in text[seed_idx : seed_idx + 800]` and `assert "never overwritten" in text`. Verify: `uv run pytest tests/test_deploy.py -q` → passes.
- [ ] 6.3 `README.md` Evals section (~lines 154-158): replace the sentence "Shipped `evals/l1.json` stays unpublished/sample until an operator run on a ready index." with "Committed `evals/l1.json` is the last operator run on the published dump (published together with the dump by `scripts/publish-data.sh`); a fresh host is seeded with it and keeps its own later runs." Append to the Dump host paragraph: "`GET /evals/l1` returns the document the running process serves." Add one sentence: "`ndcg_at_5` in the committed file predates the NDCG bound fix and can exceed 1 until the next operator run." Verify: `uv run pytest tests/test_settings.py tests/test_devtui.py -q` → passes (README fence tests).
- [ ] 6.4 Sync the main spec: apply this change's `specs/evals-l1/spec.md`, `specs/assistant-ui/spec.md`, `specs/prod-smoke/spec.md` deltas to `openspec/specs/…` (replace the MODIFIED requirement bodies, add the ADDED one) — or run `/opsx:sync` if available.

## 7. Gates

- [ ] 7.1 `uv run ruff check .`; `uv run mypy src`; `uv run pytest -q --cov=src --cov-report=term-missing` → green, ≥ 80%.
- [ ] 7.2 Operator check: `curl -s http://127.0.0.1:8000/evals/l1 | python -m json.tool | head` shows the committed document; in the UI, expand Calidad L1 → "Generación (n=30)", "137653 ms", "Juez: grok-4.3 · omitido (missing_extra)".
