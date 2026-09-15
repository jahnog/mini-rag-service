## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. The observatory still uses dark glass, a teal grid, and cyan CTAs, so a payments/FX person sees a night-mode lab instead of the navy-and-gold editorial chrome they already trust on comparable research sites.

## What Changes

- Restyle the same-screen observatory to a navy page, gold primary actions, and blue links, without a second product UI.
- Drop the grid overlay, radial glows, and glass blur. Cards stay tight (8px); Enviar and suggested prompts stay pills.
- Keep Sora, Spanish copy, canned prompts, Vista names, Limpiar, login row, and first-screen composer.
- Leave OTP HTML, auth confirm pages, favicon, and `og.png` on the current teal-dark tokens.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `assistant-ui`: replace teal-glass observatory chrome with navy editorial chrome (navy background, gold primary actions, blue links) while keeping kicker labels, pill badges, and one-screen staff/usuario use.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- A second UI, English UI copy, or a design-system package.
- Changing canned prompt strings, Staff (IA) / Usuario names, Limpiar, OTP subject, inspector copy (`Guardrails`, `copy-id`), favicon, `og.png`, OTP HTML, or auth confirm pages.
- A git-flow version bump.

## Impact

- Observatory CSS and Gradio theme only (`observatory.css`, `ui/theme.py`). No RAG port, chat JSON, Blocks tree, or auth protocol change.
- Unit tests retarget CSS/theme tokens. Live Gherkin locators unchanged. `src` coverage stays >= 80%.
- No new operator command; README `## How to run` unchanged.
