## Context

See proposal.md Why and `specs/assistant-ui/spec.md` for the first-screen composer, Limpiar label, and BCRA CAMEX title.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container. `create_fastapi` still builds Blocks and calls `mount_ui`.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session, one worker, `/clear`. Untouched.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions).

Constraints: Python 3.11+ via uv; Gradio **6.x** mounted on FastAPI at `/`. Presentation kwargs stay on `mount_ui`. Observatory CSS is hatch force-included. `test_ui.py` pins chatbot `min_height`, LAYOUT_HELP (two lines, Staff/Usuario, `inspector de citas`, `Enviar`), and CSS tokens including `content: "Guardrails"`.

IBM 1–4 take/leave (unchanged): ground in dump ids + `last_refresh` / `to_as_of`; cite or abstain; deterministic finding demotion; visible guardrail log (staff). Leave multi-agent, LlamaIndex, deontic scan as v1 MUST, 1990–97 hole. Slip order: citation honesty → freeze dates → deontic scan later.

## Goals / Non-Goals

**Goals:**

- Logged-out 1280×720 shows Pregunta + Enviar without scrolling (topbar ≤ 160px; chat floor 12rem then flex).
- Login row matches Pregunta chrome (`show_label=False` + placeholders); Clear labeled Limpiar; kicker `BCRA CAMEX · extracto no oficial` with no H1 slogan.
- Hide the chat-panel trash that duplicates Clear. Enviar/Limpiar one row at 375px.
- Unit tests; `src` coverage >= 80%.

**Non-Goals (design-level):**

- New port, second UI, Next.js, design-system package.
- Changing `handle_turn`, retrieval, ingest, HTTP `ChatResponse`, canned prompts, OTP subject, Staff inspector copy, or default Usuario.
- Light theme, English copy, Leaflet/WebGL, package version bump.

## Decisions

### Decision: shrink chat floor, do not drop shell dvh

`#observatory-chat` CSS `min-height: 480px` plus `#observatory-shell` `min-height: calc(100dvh - pad)` is what pushes the composer off a 720px window. Set CSS `min-height: 12rem` and `gr.Chatbot(min_height=192)`; keep `height="100%"` and the shell dvh min-height so a tall window still fills. Update `test_ui.py` `min_height == 192`.

Alternatives: drop shell dvh (leaves a short card on a tall display); CSS-only 12rem without Python `min_height` (Gradio still emits 480).

### Decision: placeholders, not a CSS grid on the auth Row

Gradio wraps each widget in `.block`. Grid on `#auth-login-fields` will not yield four equal cells; `align-items: flex-end` is already set and still misaligns labeled slabs against buttons. Email/code use `show_label=False` and `placeholder=AUTH_EMAIL_LABEL` / `AUTH_CODE_LABEL`; keep `label=` so `AUTH_EMAIL_LABEL in labels` still passes. Same single Row. Compact `.block` padding. At `max-width: 1120px`, 2×2 wrap.

Alternatives: two nested Rows (adds height); hide labels with CSS (fragile Gradio class names).

### Decision: visible Limpiar, spec name Clear

Button value `Limpiar`, `elem_id="observatory-clear"`. Typed `/clear` unchanged. LAYOUT_HELP Usuario line says Limpiar; keep two lines starting with Staff/Usuario and `inspector de citas`. Drop “el razonamiento,” so the Staff line fits beside the radio. `#layout-toggle { align-items: center }`. Live Gherkin still clicks `#observatory-clear`.

`title_markdown` is the kicker `BCRA CAMEX · extracto no oficial` only (no H1 slogan; Pregunta placeholder keeps the CTA). Do not change `OTP_SUBJECT`.

### Decision: compact topbar, do not move auth_status

Gradio `Markdown` renders `<span class="md prose">` as `display: inline` wrapping block `<p>`/`<h1>`, which adds ~20px line-boxes above and below each topbar Markdown. Force `#observatory-topbar .md, #observatory-topbar .prose { display: block }`. `#auth-status` stays inside `#auth-login` (live locators and `auth_chrome()` unchanged). At `min-width: 1121px`, grid the four existing topbar children: `#observatory-title` | `#auth-login` on row 1, `#layout-toggle` row 2, `#observatory-freeze` row 3. Gradio’s inner `.main.fillable` defaults to `max-width: 1024px` and was squeezing the login row onto two lines; set `.gradio-container .main` / `.fillable` / `.contain` and `#observatory-shell` to `width: 100%` with `max-width: none` so the existing 1500px container can actually fill. Target logged-out topbar ≤ 160px.

Alternatives: move status onto the Vista row (Blocks churn); keep the H1 slogan on the same paragraph (wraps at 375px and duplicates the placeholder).

Hide only the chatbot **panel** Clear icon (`#observatory-chat button.icon-button` with Clear title/aria), not per-message copy. Stretch `.bot.message` for the 401 notice. Pills `flex: 1 1 18rem`. `#observatory-actions { flex-wrap: nowrap }` and drop `min-width: 7.5rem`.

Alternatives: mass-replace “Clear” in every spec scenario (noise); hide every `.icon-button` (may drop message copy).

## Risks / Trade-offs

- [Gradio still paints a 480px chat despite `min_height=192`] → CSS `min-height: 12rem !important` on `#observatory-chat`; assert both in `test_ui.py`.
- [Placeholder-only auth fields fail a11y or live locators] → `label=` remains; live `field()` already targets `textarea, input` inside `#auth-email`.
- [375px Enviar/Limpiar still wrap] → nowrap + smaller min-width; verify in browser at 375×812.
- [Gradio Markdown inline strut leaves ~40px per widget] → `display: block` on `#observatory-topbar .md`; verify topbar ≤ 160px at 1280×720.
- [Staff inspector looks unchanged] → accepted this sitting.

## Migration Plan

Deploy with the existing host unit. Rollback is the previous `observatory.css` / Blocks copy. No index rebuild, no cookie change.
