## Context

See proposal.md Why and `specs/prod-smoke/spec.md`. Sibling change `add-prod-smoke-tests` owns `--run-prod-smoke`, marker `prod_smoke`, and HTTP smoke against `PROD_BASE_URL`. Commit `f9c3a4c` added laptop `scripts/run-prod-smoke-cron.sh` with flock, a 15m `timeout`, and `scripts/notify_prod_smoke_failure.py` that mails only on non-zero exit.

Unchanged architecture:

- **Ports:** Catalog, Extractor, Index, Llm, SessionStore. Those five stay five. Notify SMTP is laptop cron only; it is not a sixth port and is not inside `bcra_rag.auth`.
- **Composition:** `build_ingest` / `build_app`; no DI container. The cron wrapper does not call `build_app`.
- **Ingest/refresh pipeline, router, chunking A/B, session memory:** untouched.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host. This change does **not** add a dump-host timer or a GitHub Actions schedule.
- **IBM 1–4 take/leave and slip order:** unchanged. Deontic scan stays slip-first in design only.

Constraints: Python 3.11+ via uv; stdlib `smtplib` already used by the notify helper; no private hostnames in tracked files; default pytest and CI stay fake-only; `src` coverage >= 80% on the fake suite.

## Goals / Non-Goals

**Goals:**

- After a completed laptop daily run, always send one `AUTH_SMTP_*` mail (OK / FAILED / TIMED OUT).
- Keep overlap skip silent (flock miss is not a completed run).
- Keep the hand-invoked `./scripts/run-prod-smoke.sh` mail-free.

**Non-Goals:**

- Changing pytest smoke scenarios, IMAP, collector poll, or the public process.
- Adding the cron wrapper to the TUI catalog.
- Failing a green smoke solely because notify SMTP is missing.
- Installing the crontab on the laptop.

## Decisions

### Decision: notify after every completed run, not only failure

`scripts/run-prod-smoke-cron.sh` today exits 0 before notify when `CODE` is 0. Drop that early exit. After appending the run log, always invoke the notify helper, then `exit "$CODE"`. Flock miss still logs `skip: already running` and exits 0 **before** pytest, with no mail.

Notify send failure still logs `notify failed` and does not replace the smoke exit code. Missing `PROD_SMOKE_NOTIFY_TO`/`LIVE_EMAIL` or `AUTH_SMTP_*` still raises in the helper.

`scripts/prod-smoke.crontab` keeps `MAILTO=` empty so cron itself does not also mail the unix user.

Alternatives: mail from `run-prod-smoke.sh` (rejected: TUI/manual runs would spam). Treat flock skip as OK mail (rejected: false heartbeat). Fail a green run when SMTP is missing (rejected: existing log-only contract).

### Decision: rename helper; subject from exit code

Rename `scripts/notify_prod_smoke_failure.py` → `scripts/notify_prod_smoke.py`. Same CLI (`--exit-code`, `--duration`, `--log`), same recipient (`PROD_SMOKE_NOTIFY_TO` else `LIVE_EMAIL`), same body (`exit=`, `duration_s=`, `timed_out=`, last 80 log lines).

Subject:

- exit `0` → `BCRA Mini-RAG production smoke OK`
- exit `124` or `137` → `BCRA Mini-RAG production smoke TIMED OUT`
- else → `BCRA Mini-RAG production smoke FAILED`

Alternatives: keep the `_failure` filename (misleading). Separate success/failure scripts (YAGNI).

### Decision: docs and unit tests only around notify

No new How-to-run fence. README production-smoke bullet, `AGENTS.md`, crontab comment, and `.env.example` on `PROD_SMOKE_NOTIFY_TO` say the daily wrapper emails on success and on failure.

`tests/test_prod_smoke_cron.py`: wrapper must not exit 0 before notify after a completed run; fake SMTP covers OK, FAILED, and TIMED OUT. Default pytest still has no live SMTP and no `--run-prod-smoke`.

## Risks / Trade-offs

- [Success mail looks like a heartbeat while cron is dead] → that is the point of mailing OK; overlap skip stays silent so a stuck lock is not OK.
- [SMTP down on a green run is still silent] → log `notify failed`; do not rewrite smoke CODE.
- [Daily OK mail is noisy] → one message per completed run; operator can filter on subject `OK`.
- [Private mailbox/host in tracked files] → keep env names only; existing layout tests stay.

## Migration Plan

Laptop crontab already points at `run-prod-smoke-cron.sh`. Deploy is not required. Rollback: previous wrapper that mailed only on failure. No dump wipe. Git-flow version bump stays after `develop`, not in this change.

## Open Questions

None.
