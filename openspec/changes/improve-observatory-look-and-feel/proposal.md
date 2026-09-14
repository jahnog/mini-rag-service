## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. On the public observatory the login chrome and a 480px empty chat push Pregunta and Enviar below the fold, and the first-screen copy mixes English `Clear` with Spanish `Enviar` while the kicker says Mini-RAG and the tab says BCRA CAMEX — so a payments/FX person cannot use the tool as a one-screen assistant.

## What Changes

- Compact the same-screen observatory so the question input and Enviar remain visible with the login row on a 1280×720 viewport, without a second product UI.
- Login fields use the same compact control chrome as Pregunta (placeholder, no floating Gradio label slab) while keeping Spanish Correo / Código / Enviar código / Verificar on that row.
- The Clear control stays the Clear control (`#observatory-clear`, typed `/clear` unchanged) and SHALL be labeled **Limpiar**.
- On-screen kicker SHALL read BCRA CAMEX and unofficial extract (match the page title). OTP mail subject stays `Tu código de BCRA Mini-RAG`.
- Hide the Gradio chat-panel trash that duplicates Clear. Suggested prompts and Enviar/Limpiar stay one action row on a 375px viewport.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `assistant-ui`: same-screen composer remains reachable with login chrome; Clear control labeled Limpiar; visible kicker is BCRA CAMEX unofficial extract.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- A second UI, light theme, or English UI copy.
- Changing canned prompt strings, Staff (IA) / Usuario names, default Usuario, or unauthenticated-staff hide.
- Staff inspector copy (`Guardrails`, `copy-id`, `not enforced`), citation radio restyle, OTP subject, or a git-flow version bump.

## Impact

- Observatory CSS and Gradio Blocks chrome only (`observatory.css`, `ui/config.py`, `ui/gradio_app.py`). No RAG port, chat JSON, or auth protocol change.
- Unit tests on copy, chatbot `min_height`, and CSS tokens. Live Gherkin still clicks `#observatory-clear`. `src` coverage stays >= 80%.
- No new operator command; README `## How to run` unchanged.
