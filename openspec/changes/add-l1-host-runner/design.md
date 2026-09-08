## Context

See proposal.md Why. Behavior is in the three delta specs (`evals-l1`, `platform`, `assistant-ui`).

Product runtime already exists: five ports (Catalog, Extractor, Index, Llm, SessionStore); composition root `build_app` / `build_ingest` / `build_evals`; ingest/refresh on the dump host via systemd oneshots and `/etc/cron.d/`; Router (named Com. A / vigente / similarity; chunker B on TO + clean A’s); in-process session; Gradio on FastAPI; operator L1 as `evals/run_l1.py` writing `evals/l1.json`.

Laptop L1 is catalogued in `scripts/commands.toml` and README `### Evals`. Dump-host install is `scripts/deploy.sh` (`uv sync --frozen --no-dev`, rsync `--delete`, excludes `data/` and `.env` but not `evals/l1.json`). Staff Calidad L1 calls `load_l1` once when Gradio blocks are built, so a new JSON is invisible until uvicorn restarts. Chat MUST NOT import `bcra_rag.evals`. UI `is_sample_l1` is `unpublished or sample`; `run_l1.py` sets `unpublished=not index_ready` and scores a FakeIndex when the index is missing.

In-flight `add-rag-evals` already rewrote Calidad L1 (two headings; skipped suite labeled skipped, not 0) and the static results placeholder (judged metrics skipped, not zero). This change’s MODIFIED accordion and static-results bodies are a superset of that text. Archive `add-rag-evals` first, then this change. If the sibling archives later without the dump-host sentences, last-writer-wins will drop them.

## Goals / Non-Goals

**Goals:**

- One scorer (`evals/run_l1.py`); dump-host invocation is a helper + SSH wrapper.
- Operator `evals/l1.json` survives `deploy.sh` (exclude + unpublished-only seed-if-missing).
- Helper serializes with ingest/refresh (FD `flock`), stops/starts the API so Calidad L1 reloads.
- Docs in the same change: README How to run, catalog, fence sync, remote env seed.

**Non-Goals (design-level):**

- Second Python eval package or a “test server” CLI.
- systemd L1 unit (flags).
- Moving results under `DATA_DIR`.
- Re-reading `l1.json` on accordion expand (YAGNI if the helper restarts the API).
- Putting `phoenix-evals` on the API’s required install.
- Running `uv sync --extra phoenix-evals` from `deploy/l1.sh`.
- A host-provenance field on `l1.json` (banner follows `unpublished`/`sample`).
- Changing gold, metrics, chat `LLM_MODEL`, five ports, router, chunkers, or session TTL.
- HTTP `/evals`, Gradio Run, cron L1, CI paid L1.

## Decisions

### Decision: Same CLI, two invocation surfaces

`evals/run_l1.py` stays the only Python entry (`build_evals()`, gold beside the script, write `evals/l1.json`). Dump host runs that file with the absolute venv interpreter after `cd` to the install dir so `Settings()` loads host `.env`.

Laptop: existing `uv run python evals/run_l1.py` (TUI). Dump host: rendered `deploy/l1.sh` plus `scripts/run-l1.sh` that SSHs `sudo` the helper and forwards argv (`--retrieval-only`, `--generation-only`, `--generation-context`, `--deterministic-only`).

Alternative: systemd oneshot — rejected (cannot pass suite flags without several units). Alternative: HTTP `/evals` — rejected (evals spec: no eval HTTP surface). Alternative: run L1 inside refresh with a flag — rejected (refresh MUST NOT run L1 unless the operator opts in; keep opt-in as a separate command).

### Decision: No systemd L1 unit, no cron

Ingest/refresh are flagless oneshots started by `systemctl` and cron. L1 is operator-only with flags. The helper is invoked as `sudo __DEPLOY_DIR__/deploy/l1.sh [flags]`. `deploy.sh` still renders `__DEPLOY_DIR__` / `__DEPLOY_USER__` on `l1.sh` next to ingest/refresh helpers. Do not copy a fourth unit into systemd.

Alternative: Environment= drop-ins per flag — rejected (YAGNI).

### Decision: Flock + stop API + trap start (same as ingest)

`deploy/l1.sh`:

```
#!/bin/bash
set -euo pipefail
exec 9>/run/bcra-rag-job.lock
flock 9
trap 'systemctl start bcra-rag.service || true' EXIT
systemctl stop bcra-rag.service || true
cd __DEPLOY_DIR__
sudo -u __DEPLOY_USER__ __DEPLOY_DIR__/.venv/bin/python evals/run_l1.py "$@"
```

Do not write a bare `flock /run/bcra-rag-job.lock` line: util-linux `flock FILE` without a command or FD does not hold the lock across later commands. ingest/refresh use `exec 9>` then `flock 9`. Tests MUST assert `exec 9>` (or equivalent FD lock), flock-before-trap, and no `-n`.

L1 is an index **reader** (chat is too). Ingest/refresh **write** Chroma sqlite, which is why they already stop the API. L1 still takes the flock so 06:00 refresh does not overlap a retrieval suite, and so ingest does not overlap L1. Stopping the API is required because Gradio bakes L1 markdown at process start: without restart, staff still see the previous document. Chat is down for the whole score; in-process sessions die with the worker. `--retrieval-only` / `--deterministic-only` are the short path. The EXIT trap starts the API even if L1 fails (same as ingest).

Alternative: concurrent read + `systemctl restart` after — extra process memory on a small dump host; two-step operator error. Alternative: re-read JSON on accordion expand — Gradio change, cuttable; helper restart is enough.

### Decision: Rsync exclude + unpublished-only seed (do not move the file)

Keep the static document at `evals/l1.json` (gold stays `evals/gold.jsonl`; UI `settings.evals_dir / "l1.json"`). Add `evals/l1.json` to `deploy.sh` rsync excludes. Do **not** pass `--delete-excluded`. After the tree rsync, if dest `evals/l1.json` is missing, copy local `evals/l1.json` only when that file is unpublished or sample. If local is a published run, do not copy; dest stays missing (`load_l1` already synthesizes unpublished/sample). First deploy with a clean fixture gets the unpublished sample; later deploys leave operator numbers. Gold continues to rsync.

Do not `rsync --ignore-existing` of whatever sits in the working tree: a laptop `uv run python evals/run_l1.py` after local ingest writes `unpublished: false`. Do not `git show HEAD:evals/l1.json` (`deploy.sh` already `--exclude '.git/'` and is not a git-based installer).

`scripts/publish-data.sh` stays data-only (`/srv/bcra-mini-rag/production/current/data`). L1 helper uses the same `DEPLOY_DIR` as `deploy.sh` (`deploy/local.env`). Do not invent a second eval CLI for that data path.

### Decision: Judge extra stays skip-with-reason (helper does not uv sync)

Chat `uv sync --frozen --no-dev` unchanged (chat MUST NOT load evals). `deploy/l1.sh` does **not** run `uv sync`. Missing extra still skip-with-reason (`missing_extra`). Add commented `JUDGE_MODEL`, `JUDGE_BASE_URL`, `JUDGE_API_KEY`, `JUDGE_REASONING_EFFORT` to `deploy/env.remote.example` (no `export`; systemd `EnvironmentFile`). Existing `.env` is never overwritten. Empty `JUDGE_API_KEY` still falls back to `LLM_API_KEY` in `EvalSettings`.

The helper runs as root (`sudo`), same as ingest. `$HOME/.local/bin/uv` under sudo is `/root/.local/bin/uv`; `deploy.sh` installs uv as the SSH user. Root `uv sync` on `__DEPLOY_DIR__/.venv` can chown site-packages to root.

If extra sync is added later: `sudo -u __DEPLOY_USER__ -H` with that user’s uv, after `cd`, while the API is stopped, and MUST NOT fail the L1 write on sync failure. Operator MAY `uv sync --frozen --no-dev --extra phoenix-evals` as `__DEPLOY_USER__` outside this helper.

Alternative: always install the extra on API sync — rejected (chat stays lean).

### Decision: Banner follows the stored document

Calidad L1 MUST NOT imply it can tell dump-host JSON from a laptop published run. `is_sample_l1` is `unpublished or sample`. Process controls: a ready-index operator run on the dump is what is allowed to drop the banner there; deploy MUST NOT seed a published laptop file. After API reload, the accordion shows the stored document as-is.

### Decision: Documentation is part of the change

Catalog (`scripts/commands.toml`) is the source of README fences. Add a laptop-runnable wrapper row (`confirm = true`) with `readme_line` using `user@dump-host` (never a real hostname). Add the exact argv tuple to `ALLOWED_RUNNABLE`. Keep the four local `evals` rows. Sync fences with `uv run python scripts/devtui.py --sync`. Extend `tests/test_notes.py` operator bullets: dump-host command, unpublished without ingest, serving down for the run, sessions do not survive, API starts on L1 failure, banner follows unpublished/sample after reload, still `evals/run_l1.py` / `evals/l1.json` / `l1.log`.

TUI remains laptop/tests only. Dump-host `sudo` is the wrapper, not the picker executing `systemctl`.

### Decision: Ingest, router, session, host refresh (unchanged)

Five ports unchanged. `build_app` still MUST NOT import `bcra_rag.evals`. Ingest/refresh still write `data/bcra/current/` + `data/index/` on the dump host. Router still named-fetch / vigente / similarity. Session still in-process, last 6, TTL 1h, one worker. Daily refresh still `/etc/cron.d/` → `bcra-rag-refresh.service`. L1 is operator-only on that same dump.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Structured JSON; FastAPI; prompt with last_refresh / to_as_of | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters | Recommender |
| Vector search; parent = get_section | Second index |

### Decision: Slip order

1. Rsync exclude + unpublished-only seed for `evals/l1.json` (without this, dump-host numbers vanish or a laptop published run is installed).
2. `deploy/l1.sh` FD flock / stop / trap start / absolute venv / `"$@"`.
3. `scripts/run-l1.sh` + catalog + README How to run + `--sync`.
4. Commented `JUDGE_*` on remote env seed.

Never cut: one Python CLI; no HTTP evals; no cron L1; no CI paid run; chat does not import evals; fixture labeled unpublished; helper does not `uv sync`; src coverage >= 80%; README How to run in the same change. Deontic scan stays slip-first (not this change).

## Risks / Trade-offs

- [Deploy still clobbers JSON] → tests assert exclude + unpublished-only seed and no `--delete-excluded`.
- [Laptop published JSON shipped on first install] → copy local `evals/l1.json` only when unpublished/sample; dest-missing is acceptable. Do not commit operator JSON.
- [UI stale after L1] → helper always restarts API via trap; README says Calidad L1 reloads after the helper.
- [Not-ready run looks published] → `unpublished=not index_ready`; banner stays when unpublished/sample; README: laptop without ingest is sample.
- [OOM: second Chroma process] → stop API during L1 like ingest.
- [Chat down / sessions die] → same as ingest; README states it; short path `--retrieval-only` / `--deterministic-only`.
- [L1 fails, API stays down] → EXIT trap `systemctl start … || true` (same as ingest).
- [Flock vs 06:00 refresh or ingest] → `exec 9>` + `flock 9` on `/run/bcra-rag-job.lock`; wait, do not SIGTERM. Tests assert FD lock, not only the strings `flock` and the path.
- [Root uv sync chowns venv] → helper does not `uv sync`.
- [Wrong CWD / `.env`] → helper `cd` + absolute venv; wrapper uses `DEPLOY_DIR`.
- [Judged skip looks like failure] → skip_reason already in JSON; README: extra optional, helper does not install it.
- [sudo password] → same as ingest (`ssh -t` / NOPASSWD); wrapper documents `sudo` the helper.
- [Real hostname in README] → `user@dump-host` placeholder; tests already ban the lab hostname.
- [Paid L1 in CI] → no task runs live L1; tests parse scripts and fakes only.
- [Sibling last-writer-wins] → archive `add-rag-evals` first; this MODIFIED text supersets headings / skipped-not-zero / judged skip.

## Migration Plan

1. Deploy this change (`./scripts/deploy.sh`). Existing host `evals/l1.json` (fixture or prior run) is kept. New hosts get the local unpublished sample if dest is missing and local is unpublished/sample; otherwise dest stays missing.
2. Fill remote `LLM_API_KEY` if not already (required for generation). Optional `JUDGE_*`. Judged metrics stay skipped until the extra is installed as `__DEPLOY_USER__`.
3. Operator: `DEPLOY_HOST=user@dump-host ./scripts/run-l1.sh --retrieval-only` then full flags as needed. Serving is down for the run; API restarts even if L1 fails; staff accordion shows the stored document (banner iff unpublished/sample).
4. Later deploys leave that JSON. Rollback: revert the change; leftover helper is unused; operator JSON may remain.

## Open Questions

None that change specs. Archive `add-rag-evals` before this change. Judge extra on the host stays operator-manual, not this helper.
