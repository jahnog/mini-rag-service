## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. That chrome belongs on the staff screen; an end user asking what a circular says only needs the question, the answer, send, Clear, and samples. The assistant is one full observatory today, so a management control must switch those two layouts without a second product UI.

## What Changes

Nothing is **BREAKING**.

- Add a labeled management control on the same assistant screen that selects **Staff (IA)** (full current shell, default) or **Usuario** (end-user layout).
- Staff layout keeps freeze chips, citation inspector, per-query trust log, and Calidad L1.
- End-user layout hides that debug chrome and keeps question, conversation, Enviar, Clear, and the four canned prompts. Footer disclaimer and silencio abstain banner stay. Switching layout does not clear the session.
- Chat, retrieval, ingest, and HTTP contracts do not change. Package version bump is not this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-ui`: two layouts on one screen; default staff; end-user hides inspector, trust log, L1, and dump freeze chips; labeled Vista control stays visible in both layouts.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Login or a staff password.
- A second UI or extra route.
- Changing canned prompt text.
- Chat API, ports, ingest, or deploy units.
- Light theme or English UI copy.
- Persisting the layout across reloads.
- A git-flow version bump.

## Impact

- Gradio blocks topbar (title vs freeze chips, Vista radio + help copy) and visibility of the side inspector. Small CSS for the toggle row. Markdown helper for the always-visible title.
- Unit tests on default staff visibility, hide/show both ways, pinned Spanish copy, and existing banner / prompt / inspector / L1 / Clear contracts. `src` coverage stays >= 80%.
- No new Python dependencies. No change to the five ports, composition graph, `POST /chat`, or ingest/refresh.
- README `## How to run` is unchanged (no command added).
- Active change `refresh-chat-observatory-shell` is not archived yet. This delta is against main `assistant-ui`. Archive that change before apply so Observatory shell can be modified too; otherwise implement against current code and leave Observatory shell out of this delta.
