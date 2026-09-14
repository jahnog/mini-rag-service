## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The laptop daily production-smoke schedule already mails when the public origin fails, but a green run is silent, so a dead cron, a skipped overlap, or a missing mailbox looks the same as a healthy origin.

## What Changes

Nothing is **BREAKING** for `POST /chat`, cookies, or the observatory. Default `uv run pytest -q` and CI stay fake-only.

- After a **completed** daily production-smoke run, the schedule SHALL send mail to the configured notify address (or the live mailbox when that address is unset) when the run succeeds and when it fails, including when the run is cut off by the schedule bound.
- An overlapping skip that never started MUST NOT send that mail.
- The hand-invoked production-smoke command MUST NOT send that mail.
- Cron's own unix-user mail stays disabled. README `## How to run` names the always-on notify (no new command fence).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `prod-smoke`: the daily production-smoke schedule mails on every completed run (success and failure, including the schedule bound); an overlapping skip that never started does not mail; the hand-invoked command does not mail.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Dump-host timer or GitHub Actions schedule.
- Mailing from the TUI or the hand-invoked production-smoke command.
- Changing IMAP, collector, OTP, named Com. A, or weather smoke scenarios.
- Failing a green run solely because notify SMTP is missing.
- Installing the crontab on the laptop.

## Impact

- Laptop cron wrapper and stdlib SMTP helper. Five RAG ports and the public process are unchanged.
- README How to run, `AGENTS.md`, `.env.example` comment on the notify address. No new command fence; TUI catalog unchanged.
- Unit tests with a fake SMTP client; src coverage stays >= 80%. Do not run `--run-prod-smoke` in CI.
