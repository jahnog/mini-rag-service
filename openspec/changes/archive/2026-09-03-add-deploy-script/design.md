## Context

See proposal.md Why. Product runtime already exists: package `bcra_rag`, five ports, composition root, `jobs.ingest` / `jobs.refresh`, FastAPI+Gradio, Chroma on disk under `DATA_DIR`. Local How to run already lists `uv run` and Docker Compose. This change adds the **host** path only.

Constraints that shape it: a Linux dump host; SSH to a configured dump host; install dir supplied by the operator (`DEPLOY_DIR`, default remote `$HOME/bcra-mini-rag`); no Docker on that host; embeddings at a configured OpenAI-compatible URL (`qwen3-embedding-0.6b`); chat LLM xAI Grok; dump must survive update.

Unchanged product architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore.
- **Composition:** `build_ingest` / `build_app`; no DI container.
- **Ingest/refresh:** catalog → polite fetch → extract → index upsert → MANIFEST; refresh refuses until `last_refresh` is set.
- **Router:** aliases; named Com. A `get_section` wins over vigente; vigente → TO ∪ later A’s; else similarity.
- **Chunking:** A fixed-size vs B structure-aware; serving uses B on TO + clean A’s.
- **Session:** in-process, one worker, `/clear`.
- **Host-side refresh:** jobs run on the volume host (here systemd oneshots + cron.d), not GitHub Actions.

## Goals / Non-Goals

**Goals:**

- Workstation `scripts/deploy.sh` rsyncs the tree, bootstraps the box, installs committed unit/cron files, restarts one uvicorn worker.
- Update is the same command; `data/` and `.env` are never overwritten.
- Ingest/refresh are oneshot units that stop the API, run the existing modules, start the API (including on failure).
- Daily refresh via `/etc/cron.d/`, not a systemd timer.
- README How to run lists deploy, update, SSH local-forward, ingest/refresh.

**Non-Goals (design-level):**

- Changing ports, router, chunkers, Gradio, or ingest Python.
- Docker on the dump host.
- Reverse SSH for embeddings; starting llama.cpp from this command.
- TLS, publishing `:8000`, user lingering systemd.

## Decisions

### Decision: uv + systemd on the host, Docker only locally

A small dump host plus a remote embedding hop made Docker a tax (dockerd RAM, `host.docker.internal`). Host `uv sync --frozen --no-dev`, `apt install poppler-utils`, and a system unit match How to run’s first-class `uv run` path.

Alternatives: Compose on the VPS (rejected); Nix/Podman (not smaller).

### Decision: Committed `deploy/` templates, rendered at deploy time

| File | Role |
|---|---|
| `scripts/deploy.sh` | Requires `DEPLOY_HOST`. Optional `DEPLOY_USER` / `DEPLOY_DIR` (or gitignored `deploy/local.env`). Default dir is remote `$HOME/bcra-mini-rag`. Bootstrap, rsync (no `--delete-excluded`), `$HOME/.local/bin/uv sync --frozen --no-dev`, render `__DEPLOY_USER__` / `__DEPLOY_DIR__`, install units + cron.d, `daemon-reload`, `enable`, **`restart` API**. `--ingest` waits on `systemctl start bcra-rag-ingest`. |
| `deploy/bcra-rag.service` | `User=__DEPLOY_USER__`, `WorkingDirectory=__DEPLOY_DIR__`, `EnvironmentFile=__DEPLOY_DIR__/.env`, ExecStart `__DEPLOY_DIR__/.venv/bin/uvicorn bcra_rag.api.app:app --host 127.0.0.1 --port 8000` (no `--workers`), `Restart=always`, `[Install] WantedBy=multi-user.target`. No `Conflicts=`. |
| `deploy/bcra-rag-ingest.service` / `bcra-rag-refresh.service` | `Type=oneshot`, **root**, `WorkingDirectory=__DEPLOY_DIR__`, `TimeoutStartSec=infinity`, **no** `Conflicts=`, no `[Install]`, `ExecStart=` helper script. |
| `deploy/ingest.sh` / `refresh.sh` | `flock /run/bcra-rag-job.lock`; `trap` `systemctl start bcra-rag` on EXIT; stop API; `cd` to deploy dir; `sudo -u` the service user, **absolute** `.venv/bin/python -m bcra_rag.jobs.{ingest,refresh}`. |
| `deploy/bcra-rag-refresh.cron` | `0 6 * * * root systemctl start bcra-rag-refresh.service` → `/etc/cron.d/bcra-rag-refresh`. |
| `deploy/env.remote.example` | Seed remote `.env`: `EMBEDDING_BASE_URL=http://127.0.0.1:8001/v1`, `EMBEDDING_MODEL=qwen3-embedding-0.6b`, `EMBEDDING_API_KEY=sk-local`, xAI LLM defaults, empty `LLM_API_KEY`. |

Rsync excludes `.git/`, `.venv/`, `data/`, `__pycache__/`, `.env`, `.envrc`, `deploy/local.env`, `coverage.xml`, `.coverage` and MUST NOT pass `--delete-excluded` (that flag would delete excluded dest dirs). Optional `--delete` is fine.

Alternatives: generate units only as heredocs (drift); user crontab (cannot start a system unit without sudoers); systemd timer (operator asked for crontab).

### Decision: Root oneshots, EXIT trap, flock, infinite start timeout

The service user cannot `systemctl stop` the API unit. Default `TimeoutStartSec=90s` would kill first ingest. `ExecStartPost` is skipped if the job fails, so the helper always restarts the API via `trap`.

Do **not** `Conflicts=` the API (or ingest vs refresh). `Conflicts=` is bidirectional: `trap systemctl start bcra-rag` while the oneshot is still `activating` queues a stop of that job, hangs `--ingest`, or leaves the API down. Helpers already stop the API. Serialize ingest vs refresh with `flock /run/bcra-rag-job.lock` so 06:00 **waits** instead of SIGTERM-ing a long first ingest.

Cron PATH is empty and `sudo -u` resets env: `cd` to the install dir then call the **absolute** venv python. All three units set `WorkingDirectory` to that dir. API `EnvironmentFile` is the absolute `.env` path (relative `.env` is `/.env`).

`--ingest` is `ssh sudo systemctl start bcra-rag-ingest` (oneshot waits). Do not invoke the job module from `deploy.sh` a second way.

### Decision: enable + restart, `[Install]` on the API only

`systemctl enable --now` does not restart an already-active uvicorn, so a second deploy would rsync code while the worker kept old imports. After installing units: `daemon-reload`, `enable bcra-rag`, **`restart bcra-rag`**. The API unit MUST have `[Install] WantedBy=multi-user.target` or `enable` fails and boot start is missing. Oneshots have no `[Install]`.

### Decision: Bind 127.0.0.1:8000; embeddings off the dump host

UI via `ssh -L 8000:127.0.0.1:8000 user@dump-host`. The embedding server is a configured OpenAI-compatible endpoint (not installed on the dump host). Chroma `OpenAIEmbeddingFunction` already takes `api_base`; empty `EMBEDDING_API_KEY` still selects the 8-d deterministic function, so the seed dummy key is required. No Python change.

Alternatives: reverse SSH to loopback; bind `0.0.0.0` (accidental public exposure).

### Decision: First `.env` from remote seed, never overwrite

If remote `.env` is missing, copy `deploy/env.remote.example` and exit non-zero until `LLM_API_KEY` and `EMBEDDING_API_KEY` are non-empty. Later deploys leave `.env` and `data/` alone. systemd `EnvironmentFile` forbids `export`. `DATA_DIR=data` is relative to `WorkingDirectory`.

### Decision: Bootstrap poppler and uv

Idempotent SSH: `poppler-utils`, `uv` in `~/.local/bin` if missing. Swap and memory caps are host provisioning, not this script. Every remote `uv` invocation uses `$HOME/.local/bin/uv` (or `PATH="$HOME/.local/bin:$PATH"`); non-interactive SSH does not source bashrc. Passwordless sudo assumed; `ssh -t` if sudo needs a TTY. Host Python 3.12 is enough (`requires-python >= 3.11`).

### Decision: IBM 1–4 take/leave (this slice)

| Take | Leave |
|---|---|
| Host-side dump + refresh on the volume host | GHA-hosted Chroma; Docker on the dump host |
| One worker, in-process session | Redis; multi-replica |
| OpenAI-compatible remote embeddings + Grok | llama.cpp on the dump host; LlamaIndex |
| Existing chunkers / router | Second index; FAISS |

Deontic scan stays slip-first (not this change).

### Decision: Slip order

Never cut: one worker; rsync exclude of `data/` and `.env` without `--delete-excluded`; health HTTP 200 on empty dump; oneshot `TimeoutStartSec=infinity`; no `Conflicts=` vs API; API restart after failed job **and** after update; `[Install]` on the API unit; README How to run.

## Risks / Trade-offs

- [OOM during `uv sync` or ingest] → stop API during jobs; optional host-local memory cap / swap.
- [Empty embedding key → fake 8-d index] → fail deploy if `EMBEDDING_API_KEY` empty; seed `sk-local`.
- [Embedding endpoint down or bound to localhost only] → ingest/search fail; named Com. A `get_section` still works without vectors.
- [sudo password] → `ssh -t`; document NOPASSWD.
- [cron.d files with dots ignored] → dest name `/etc/cron.d/bcra-rag-refresh` (no dot).
- [First ingest lasts hours] → `TimeoutStartSec=infinity`; `--ingest` is opt-in; `flock` so 06:00 waits.
- [Chroma sqlite vs two processes] → stop API around jobs (not `Conflicts=`).
- [Oneshot `Conflicts=` + trap start API] → no `Conflicts=`; trap + helper stop only.
- [Relative EnvironmentFile / CWD `/`] → absolute `.env` and WorkingDirectory on all units; helpers `cd` + absolute venv.
- [`enable --now` leaves old uvicorn] → `restart` after every deploy.
- [Accidental public UI] → bind 127.0.0.1 only.

## Migration Plan

1. Operator fills `LLM_API_KEY` after first deploy seeds `.env`.
2. `DEPLOY_HOST=user@dump-host ./scripts/deploy.sh` then the same with `--ingest` while the embedding server is up.
3. Update: `./scripts/deploy.sh` again (with `DEPLOY_HOST` or `deploy/local.env`).
4. Rollback: `systemctl disable --now bcra-rag`; leave `data/` on disk. No user data in git.

## Open Questions

None. Host, paths, embedding URL/model, bind address, and cron vs timer are operator-configured or decided as above.
