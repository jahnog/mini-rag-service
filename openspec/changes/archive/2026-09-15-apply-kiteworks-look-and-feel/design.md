## Context

See proposal.md Why and `specs/assistant-ui/spec.md` for light editorial chrome on the same-screen observatory.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container. `create_fastapi` still builds Blocks and calls `mount_ui`.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session, one worker, `/clear`. Untouched.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions).

Constraints: Python 3.11+ via uv; Gradio **6.x** mounted on FastAPI at `/`. Presentation kwargs stay on `mount_ui`. Observatory CSS is hatch force-included. `test_ui.py` pins CSS tokens, theme-color, and `observatory_js()`.

IBM 1–4 take/leave (unchanged): ground in dump ids + `last_refresh` / `to_as_of`; cite or abstain; deterministic finding demotion; visible guardrail log (staff). Leave multi-agent, LlamaIndex, deontic scan as v1 MUST, 1990–97 hole. Slip order: citation honesty → freeze dates → deontic scan later.

## Goals / Non-Goals

**Goals:**

- Navy page, gold primary fill, blue links; drop grid overlay, radial glows, and glass blur.
- Cards 8px; Enviar and suggested prompts stay 999px pills.
- Keep Sora, Blocks tree, first-screen composer, Limpiar.
- Unit tests retarget tokens; `src` coverage >= 80%.

**Non-Goals (design-level):**

- New port, second UI, Next.js, design-system package, font swap.
- Changing `handle_turn`, retrieval, ingest, HTTP `ChatResponse`, canned prompts, OTP HTML, auth confirm pages, favicon, or `og.png`.
- English copy or a package version bump.

## Decisions

### Decision: retint existing CSS rules, do not rewrite the stylesheet

`:root` tokens are not enough. Bubbles, pills, chips, secondary buttons, and the abstain banner hardcode dark `rgba(...)`. Edit those existing selectors. Delete `body::after` (grid). Split `#observatory-footer` out of the glass panel group so it can be navy `#121548`. Keep `#observatory-*` ids; do not add article sections.

Tokens from the live Kiteworks article: page `#050821`, panels `#121548`, gold `#f4b223`, blue `#425cc7`, muted `#b5c5e8`. Gold is fill only.

Alternatives: new CSS file (hatch + tests churn); font swap to Merriweather/Source Sans (extra theme surface, rejected).

### Decision: force navy Gradio fills and keep the dark class

`theme.py` constants follow the same hex. `PRIMARY_FILL` is flat `#f4b223`. `.set()` writes both default and `_dark` keys so OS light cannot leak gray chrome. `primary_hue` amber, `secondary_hue` blue, `block_radius="8px"`, keep `GoogleFont("Sora")`. `observatory_js()` keeps title, `lang="es"`, and `classList.add("dark")`. CSS `button.primary` and `.observatory-pill` stay `border-radius: 999px` so Enviar does not become an 8px box.

`THEME_COLOR` / theme-color meta: `#050821`.

Alternatives: a white page (the live Kiteworks article is navy, not white); restyle OTP/favicon in the same sitting (out of scope).

### Decision: leave mail, confirm pages, and marks on teal-dark tokens

OTP HTML, `/auth/link` pages, favicon, and `og.png` stay `#04111d` / `#72d6cb`. The observatory is the product screen; those surfaces are extra files.

Alternatives: retint them in this change (larger diff); a shared token module (YAGNI for four hex constants).

## Risks / Trade-offs

- [Hardcoded dark rgba missed] → checklist is the existing bubble/pill/chip/abstain/secondary selectors; browser-use on 1280 and 375 is the proof.
- [OS dark paints Gradio gray] → light `_dark` fills + `color-scheme: light` + no JS `dark` class.
- [8px `block_radius` boxes Enviar] → CSS pill radius on primary and `.observatory-pill`.
- [Gold text on white] → gold is button fill; text stays navy.
- [Tab icon and OTP mail still teal] → accepted this sitting.

## Migration Plan

Deploy with the existing host unit. Rollback is the previous `observatory.css` / `theme.py`. No index rebuild, no cookie change.
