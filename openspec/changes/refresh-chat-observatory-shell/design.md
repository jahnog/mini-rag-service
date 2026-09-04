## Context

See proposal.md Why and `specs/assistant-ui/spec.md` for the one-screen contract.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container. `create_fastapi` still builds Blocks and calls `mount_ui`.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session, one worker, `/clear`. Untouched.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions).

Constraints: Python 3.11+ via uv; Gradio **6.26** mounted on FastAPI at `/` (`gr.mount_gradio_app`), not `launch()`. In Gradio 6, `theme` / `css` / `css_paths` / `head` / `footer_links` / `run_history` belong on `mount_gradio_app`. Current UI is a single-column default stack in `src/bcra_rag/ui/gradio_app.py` (banner markdown, chatbot, textbox, Enviar/Clear, `gr.Examples`, citation Radio + JSON, trust JSON, collapsed L1, footer). Hatchling wheels include `.py` only unless force-included.

Visual references (layout from Climate Observatory, control chrome from Barnes-Hut) are CSS/HTML identity only. Do not import their runtimes.

## Goals / Non-Goals

**Goals:**

- Observatory shell around the existing Gradio chat: topbar freeze chips, dominant stage, side inspector, footer.
- Dark teal/glass chrome; citation cards + trust chips as the visible inspector; copy-id via Gradio copy button.
- Unit tests on helpers, CSS tokens, mount kwargs, and `elem_id`s. `src` coverage >= 80%.

**Non-Goals (design-level):**

- New port, second UI, Next.js, or a design-system package.
- Changing `handle_turn`, retrieval, ingest, HTTP `ChatResponse`, or canned prompt strings.
- Light theme, English copy, Leaflet/WebGL.
- Package version bump (`release/0.6.0` after this lands on develop).

## Decisions

### Decision: Presentation kwargs only on `mount_ui`

`build_blocks` owns layout, `elem_id` / `elem_classes`, and event wiring. `mount_ui` is the only place that passes Gradio 6 presentation:

```python
gr.mount_gradio_app(
    api, blocks, path="/",
    theme=observatory_theme(),
    css_paths=observatory_css_path(),
    head=observatory_head(),
    footer_links=[],
    run_history=False,
)
```

Extract `observatory_theme()`, `observatory_css_path()`, `observatory_head()` (new `src/bcra_rag/ui/theme.py`) so tests assert without mounting FastAPI.

`observatory_head()` is `<meta name="theme-color" content="#04111d">`. Sora is loaded by `gr.themes.GoogleFont("Sora")`; CSS lists `Sora, "Segoe UI", sans-serif` so tests do not need fonts.googleapis.com.

`footer_links=[]` and `run_history=False` keep “Built with Gradio” / run history off the observatory footer.

Alternatives: `theme=` on `gr.Blocks(...)` (deprecated in Gradio 6, warns); a static HTML shell around Gradio (second UI); Next.js (v1 non-goal).

### Decision: CSS file + hatch force-include

New `src/bcra_rag/ui/observatory.css`, loaded with `Path(__file__).with_name("observatory.css")`. Host deploy copies the `src` tree. Hatchling would drop the file from a wheel, so:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/bcra_rag/ui/observatory.css" = "bcra_rag/ui/observatory.css"
```

CSS targets stable `#observatory-*` ids, not hashed Gradio classes. Tokens: background `#04111d` → `#020811`, accent `#72d6cb` / `#9ce7df`, gold `#ffd27d`, pass `#8ff5d1`, warn `#ffc16d`, block `#ff8f9d`, glass 28px, `color-scheme: dark`, faint grid overlay, `rise-in`. Wide layout uses Gradio `Row`; stacking at 1120px is `flex-wrap` on `#observatory-layout` (Gradio Row is flex, not the climate site’s CSS grid).

Theme: `gr.themes.Base(primary_hue=teal, secondary_hue=sky, neutral_hue=slate, font=GoogleFont("Sora"))` then `.set(...)` dark body/block/input/button fills so unstyled chrome is not light-gray.

Alternatives: CSS as a Python string (avoids hatch, worse editing); copying the reference CSS files (class names will not match).

### Decision: Blocks tree is the shell

```
gr.Blocks(title="BCRA Mini-RAG", fill_height=True)
  Column#observatory-shell
    Markdown#observatory-topbar
    Row#observatory-layout
      Column#observatory-stage (scale=3, min_width=0)
        Markdown#abstain-banner
        Chatbot (show_label=False)
        Pregunta + Enviar (primary) / Clear (secondary)
        Demo key if DEMO_API_KEY
        four canned-prompt Buttons
      Column#observatory-side (scale=2, min_width=320)
        Radio citation cards + Markdown#citation-card
        Textbox copy-id (interactive=False, buttons=["copy"])
        Markdown#trust-panel
        Accordion "Calidad L1" open=False
        JSON inspector + trust, visible=False
    Markdown#observatory-footer
```

Canned prompts: one `gr.Button` per `CANNED_PROMPTS` item; click fills the pregunta box. Do not use `gr.Examples` (it will not restyle into pills).

JSON widgets stay in the `_turn` graph with `visible=False` so return shape can stay; they are not the inspector.

Copy-id uses Gradio’s built-in copy button (satisfies clipboard without custom JS).

Helpers in `ui/config.py`: `topbar_markdown(health)` (kicker + title + freeze chips; keep `banner_markdown` returning the same freeze fields so existing tests still pass) and `trust_markdown(rows)` (rule / verdict chips). `citation_card_markdown` unchanged in contract.

`_turn` / `_clear` / `_select_card` keep the same session, citation, trust, and abstain behavior.

Alternatives: restyle the current single column only (fails the stage+side contract); Dataset/Gallery for cards (YAGNI — Radio + markdown already select in place).

### Decision: Tests inspect helpers and the Blocks tree, not GET `/`

- CSS file contains `#04111d`, `#72d6cb`, `28px`.
- Theme/head/css-path helpers and `mount_ui` kwargs (`css_paths`, `theme`, `head`, `footer_links=[]`).
- Walk Blocks for `elem_id`s (`observatory-shell`, `observatory-topbar`, `observatory-layout`, `observatory-stage`, `observatory-side`, `abstain-banner`, `citation-card`, `trust-panel`, `observatory-footer`).
- Existing `banner_markdown` / canned prompts / L1 collapsed / inspector copy-id / trust / abstain / `build_blocks` does not call L1.

Do not make CI depend on Gradio SSR HTML from `TestClient` GET `/`. Browser check is apply-time only.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| 1 Ground in dump ids + `last_refresh` / `to_as_of` | Multi-agent / HITL |
| 2 Cite or abstain | LlamaIndex / second index |
| 3 Deterministic finding demotion after generation | Deontic scan as v1 MUST |
| 4 Visible guardrail log | Filling 1990–97 hole |

Slip order (design only): citation honesty → freeze dates → deontic scan later. Deontic scan stays slip-first, not this change.

## Risks / Trade-offs

- [Gradio wrapper DOM shifts] → Style `#observatory-*` ids and theme fills, not hashed class names.
- [OS light preference paints Gradio light] → `color-scheme: dark` plus `.set()` dark fills.
- [Wheel drops the CSS] → hatch `force-include`; `Path(__file__)` for source and deploy.
- [JSON still in the graph] → `visible=False`; markdown/cards are the inspector.
- [Google Fonts unreachable] → CSS fallback stack; tests never fetch the font.
- [flex-wrap stacks poorly] → 1120px media query on `#observatory-layout`; side `min_width=320`.

## Migration Plan

Deploy the serving process (one worker) as today. No dump wipe, no index rebuild, no env key change. Rollback: previous `gradio_app.py` mount without theme/css. Git-flow `release/0.6.0` (pyproject + FastAPI `version=` + tag) happens after this change is on `develop`, not in this change.
