## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The assistant already puts those on one screen, but that screen is a default stacked chat, so a reviewer does not see the freeze chips, cited clause, this-query trust log, and last L1 inside a shell that reads as one product.

## What Changes

Nothing is **BREAKING**.

- Wrap the existing assistant in a dark observatory shell: topbar freeze chips, a dominant chat stage, a side inspector, and a footer disclaimer.
- Citation cards and trust chips become the visible inspector. Copy-id stays a clipboard control for the dump document id.
- The same four canned prompts stay; they are shown as pills on the chat stage.
- The abstain banner stays on the chat stage when finding is silencio. Calidad L1 stays collapsed and static.
- Chat, retrieval, ingest, and HTTP contracts do not change. Package version bump is not this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-ui`: one-screen observatory shell (topbar freeze chips, dominant chat stage, side inspector, footer); citation cards and trust chips as the visible inspector; copy-id on the clipboard; dark observatory chrome without a second product UI.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- A second UI or a reusable design-system package.
- Leaflet, Scala.js, WebGL, or copying the reference sites’ visualization runtimes.
- Light theme or English UI copy.
- Changing canned prompt text.
- Chat API, ports, ingest, or deploy units.
- A git-flow version bump (that is `release/0.6.0` after this change lands on develop).

## Impact

- Gradio blocks layout and mount presentation (theme, CSS, head). Markdown helpers for the topbar and trust chips.
- Unit tests on shell structure, CSS tokens, mount kwargs, and existing banner / prompt / inspector / L1 / Clear contracts. `src` coverage stays >= 80%.
- No new Python dependencies. No change to the five ports, composition graph, `POST /chat`, or ingest/refresh.
- README `## How to run` is unchanged unless a command is added (none expected).
