## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. Optional traces and L1 annotations already go to a collector endpoint, but that endpoint now requires an API key, so spans and annotations are dropped while chat and the static L1 file still succeed.

## What Changes

Nothing is **BREAKING** for `POST /chat` or for the L1 operator command.

- When a collector endpoint is configured, the serving process MAY also send a configured API key on exported traces.
- When a collector endpoint is configured, an operator L1 run MAY send the same key on annotation export.
- An unset key still talks to an unauthenticated collector (local sibling process). A missing extra, missing key, or collector auth failure MUST NOT fail chat or the static L1 write.
- Default automated tests MUST NOT require a live collector or a real key.
- README `## How to run` Debug and Evals name the optional key (no new command fence).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `platform`: optional collector MAY authenticate with a configured API key; unset key still exports to an unauthenticated collector; export remains fail-open; tests MUST NOT require a live collector or a real key.
- `evals-l1`: a collector auth failure MUST NOT fail the static L1 write (same fail-open as a down collector).

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Requiring a key whenever the collector is set.
- Phoenix Cloud-only custom client headers.
- Adding collector fields to chat settings.
- Promoting collector SDKs out of optional extras.
- HTTP eval API, Gradio “Run L1”, or scoring in the browser.

## Impact

- Chat tracer and L1 annotation sink pass the configured key when present. Chat `POST /chat` contract, five ports, and extras `otel` / `phoenix-evals` stay. The wrong top-level `phoenix` package is not added.
- `.env.example`, remote env seed, and README How to run document the optional key.
- Unit tests with fakes; src coverage stays >= 80%. No live collector and no paid L1 in CI.
