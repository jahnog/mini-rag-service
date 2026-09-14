## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The public observatory has no page-view collector, and the analytics server has no site for that origin, so visits never show up next to the other product sites.

## What Changes

Nothing is **BREAKING** for `POST /chat`, cookies, or the observatory layout. Default `uv run pytest -q` and CI stay fake-only.

- Create one analytics site for the public observatory origin on the existing collector (idempotent: reuse if that origin already has a site).
- When a tracker origin and site id are configured, the observatory page SHALL send a cookieless page view to that collector. Unset or invalid config injects nothing. Loopback hosts send nothing unless the operator forces it.
- Mail-link pages stay untracked. Mailbox and question text MUST NOT be sent.
- README How-to-run and env examples document the two optional keys. No new operator command.

## Capabilities

### New Capabilities

- `web-analytics`: optional cookieless page-view tracking on the observatory when a tracker origin and site id are configured; fail-open when unset or invalid; loopback skipped; no mailbox or question text; mail-link pages untracked.

### Modified Capabilities

- (none)

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Custom events, Goals, a noscript pixel, a cookie banner, or a first-party tracker proxy.
- Tracking mailbox, question text, or mail-link pages.
- Naming the public hostname or tracker host in tracked files.
- Changing Phoenix / OTLP, Gradio’s own telemetry, or the five RAG ports.
- A second UI, live-server / prod-smoke / paid L1 as a required gate, or a new operator command.

## Impact

- Observatory `head` HTML and chat `Settings` gain two optional keys. Auth CSP and mail-link pages unchanged.
- Unit tests on snippet present/absent and sanitization. Default pytest never talks to the collector. `src` coverage stays >= 80%.
- Operators set the tracker origin and site id on the dump-host `.env` and restart the serving unit. Existing remote `.env` is not overwritten by deploy.
