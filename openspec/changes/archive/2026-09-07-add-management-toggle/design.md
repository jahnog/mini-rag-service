## Context

See proposal.md Why and `specs/assistant-ui/spec.md` for the two-layout contract.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container. `create_fastapi` still builds Blocks and calls `mount_ui`.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session, one worker, `/clear`. Untouched.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions).

Constraints: Python 3.11+ via uv; Gradio **6.x** mounted on FastAPI at `/` (`gr.mount_gradio_app`), not `launch()`. Presentation kwargs stay on `mount_ui`. Current UI is the observatory shell in `src/bcra_rag/ui/gradio_app.py` (topbar, stage, side inspector, footer). Hatchling wheels include `.py` only unless force-included; `observatory.css` is already force-included.

Active change `refresh-chat-observatory-shell` implemented that shell but is not archived. This design targets that code as the staff layout. Archive it before apply when possible so main specs include Observatory shell.

## Goals / Non-Goals

**Goals:**

- One Blocks tree with a labeled Vista radio (default Staff (IA)) that hides/shows debug chrome.
- End-user layout: question, chat, Enviar, Clear, samples; freeze chips and `#observatory-side` hidden; footer and silencio abstain banner stay.
- Unit tests on default visibility, hide/show, pinned copy, and existing UI contracts. `src` coverage >= 80%.

**Non-Goals (design-level):**

- New port, second UI, extra route, Next.js, or a design-system package.
- Changing `handle_turn`, retrieval, ingest, HTTP `ChatResponse`, or canned prompt strings.
- Login, env `UI_MODE`, query-param deep link, or persisting the choice across reload.
- Light theme, English copy, Leaflet/WebGL.
- Package version bump.

## Decisions

### Decision: one tree + `layout_updates(staff: bool)`

Keep a single `gr.Blocks` tree. Hide debug regions with Gradio `visible=False` so they leave the flex row. Do not mount a second app.

```python
LAYOUT_STAFF = "Staff (IA)"
LAYOUT_USER = "Usuario"
LAYOUT_HELP = (
    "Staff (IA) muestra el inspector de citas, el log de guardrails, "
    "Calidad L1 y las fechas del dump. Usuario deja solo la pregunta, "
    "la respuesta, Enviar, Clear y los ejemplos."
)

def layout_updates(staff: bool) -> tuple[Any, Any]:
    return gr.update(visible=staff), gr.update(visible=staff)
```

Radio `.change` maps the choice to `staff = (value == LAYOUT_STAFF)` and returns those two updates for `#observatory-freeze` and `#observatory-side`. The handler MUST NOT write chatbot history or `session_state`.

Alternatives: two Gradio apps / two routes (second UI, spec forbids); CSS-only hide (widgets still take layout); env `UI_MODE` (restart to switch); URL `?staff=1` (custom JS).

### Decision: Vista radio + pinned help, default staff

Topbar structure:

```
Column#observatory-topbar
  Markdown title                 # title_markdown(health); always
  Row#layout-toggle
    Radio label="Vista", choices=[Staff (IA), Usuario], value=Staff (IA)
    Markdown#layout-toggle-help  # LAYOUT_HELP
  Markdown#observatory-freeze    # banner_markdown(health); visible in staff
Row#observatory-layout
  Column#observatory-stage       # always (abstain, chat, pregunta, Enviar/Clear, demo key, pills)
  Column#observatory-side        # visible in staff
Markdown#observatory-footer      # always
```

Radio choices *are* the names of the layouts. Help markdown states what changes. Both stay visible in Usuario so the user can switch back.

Keep `banner_markdown` and `topbar_markdown` freeze-field contracts (`test_banner_and_canned_prompts`). Add `title_markdown(health)` for the always-visible kicker + H1 + unofficial extract wording without freeze chips. `topbar_markdown` may remain `title + banner` so existing helper tests still pass; the UI uses two widgets.

Demo key stays in the stage, `visible=bool(settings.demo_api_key)`, both layouts (access, not debug). JSON inspector/trust stay `visible=False`. `_turn` / `_clear` / `_select_card` outputs unchanged.

CSS in `observatory.css` for `#layout-toggle` / `#layout-toggle-help` (already hatch force-included). When side is hidden, stage fills the row. 1120px wrap unchanged for staff.

Alternatives: checkbox “Modo gestión” (does not name both layouts); hiding the control in Usuario (cannot switch back).

### Decision: tests inspect helpers and the Blocks tree, not GET `/`

- Constants `LAYOUT_STAFF`, `LAYOUT_USER`, `LAYOUT_HELP` exist; help and both choice strings appear on the Blocks tree (`#layout-toggle`, `#layout-toggle-help`).
- Default `build_blocks`: `#observatory-side` and `#observatory-freeze` visible; existing observatory `elem_id`s still present.
- `layout_updates(False)` hides freeze + side; `True` shows them. The radio change handler does not clear session/history.
- Existing inspector / trust / abstain / L1 collapsed / copy-id / no-`gr.Examples` / JSON hidden tests stay.
- No Gherkin change (`chat.feature` is HTTP). Do not make CI depend on Gradio SSR HTML from `TestClient` GET `/`.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| 1 Ground in dump ids + `last_refresh` / `to_as_of` | Multi-agent / HITL |
| 2 Cite or abstain | LlamaIndex / second index |
| 3 Deterministic finding demotion after generation | Deontic scan as v1 MUST |
| 4 Visible guardrail log (staff surface) | Filling 1990–97 hole |

Slip order (design only): citation honesty → freeze dates → deontic scan later. Deontic scan stays slip-first, not this change.

## Risks / Trade-offs

- [`refresh-chat-observatory-shell` archived after this change] → Archive it first when possible; otherwise this delta does not MODIFY Observatory shell and implementers still hide `#observatory-side` in code.
- [Gradio `Column(visible=False)` still occupies the row] → Assert side `visible is False`; if the stage does not expand, add a CSS fallback on `#observatory-layout`.
- [Hiding freeze chips also hides unofficial wording] → Title markdown and footer keep “no oficial”; only `#observatory-freeze` (`banner_markdown`) hides.
- [Toggle handler accidentally returns `_clear` outputs] → Handler returns only freeze + side updates.
- [OS / Gradio radio restyle] → Style `#layout-toggle`, not hashed classes.

## Migration Plan

Deploy the serving process (one worker) as today. No dump wipe, no index rebuild, no env key change. Default remains the current staff shell, so first paint matches today’s UI. Rollback: previous `gradio_app.py` topbar without the radio. Git-flow version bump happens after this change is on `develop`, not in this change.

## Open Questions

None. Copy, default, and visibility list are pinned above.
