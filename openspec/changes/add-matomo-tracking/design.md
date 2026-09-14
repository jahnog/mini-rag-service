## Context

See proposal.md Why and `specs/web-analytics/spec.md`.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index, Llm, SessionStore. This change does not add a port.
- **Composition:** `build_ingest` / `build_app`; no DI container.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process session (last six messages), one worker, `/clear`.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions). API unit `EnvironmentFile` is the install dir `.env`.

Today the observatory `head` (`observatory_head()` passed to `gr.mount_gradio_app(..., head=...)`) has title, favicon, OG tags, and a lang script. There is no Matomo/`_paq` code. Auth mail-link HTML has CSP `default-src 'none'`. Phoenix OTLP is server-side chat traces. The Matomo MCP has no site whose main URL is the public observatory origin.

## Goals / Non-Goals

**Goals:**

- Idempotent Matomo site for the public origin (timezone `America/Argentina/Buenos_Aires`).
- Cookieless JS tag in `observatory_head` when `MATOMO_URL` + `MATOMO_SITE_ID` are valid.
- Fail-open sanitization; loopback skip unless `?matomo=1`.
- Unit tests; `src` coverage >= 80%. Tracked files never name the public host.

**Non-Goals:**

- Custom events, Goals, noscript pixel, cookie banner, first-party proxy.
- Tracking `/auth/link*`, mailbox, or chat text.
- `enableJSErrorTracking` (Gradio noise).
- Phoenix / Gradio telemetry changes.
- A sixth port; Matomo keys on `AuthSettings` or `EvalSettings`.

## Decisions

### Decision: snippet in Gradio `head`, not HTML rewrite middleware

Gradio 6 documents `head` as the place for extra `<script>` tags. The existing lang script already executes from `observatory_head()`. `_RewriteGradioHtml` runs on every `text/html` response, including `/auth/link`, so injecting there would hit CSP pages and token URLs.

`mount_ui(api, blocks, settings=None)` passes `settings.matomo_url` / `settings.matomo_site_id`. No settings ⇒ today’s head (existing unit test).

Alternatives: first-party reverse proxy (ops, out of v1); middleware inject (hits auth pages).

### Decision: chat `Settings` fields, fail-open sanitize

`MATOMO_URL` / `MATOMO_SITE_ID` on chat `Settings` because the UI process reads them (unlike Phoenix eval keys). Empty default. Valid URL: https, host, no userinfo, no whitespace/`'"<>\\`. Site id: digits. Normalize trailing `/`. Invalid → omit snippet.

Loopback gate is inside the IIFE (`localhost`, `127.0.0.1`, `::1`, `[::1]`) unless `?matomo=1`, so live Gherkin on loopback stays quiet even if laptop `.env` has keys.

Snippet: `disableCookies`, `setDoNotTrack`, `setTrackerUrl` `{url}matomo.php`, `setSiteId`, `enableLinkTracking`, `enableHeartBeatTimer` 15, `trackPageView`, async `{url}matomo.js`.

Alternatives: honor DNT off (rejected: sibling sites honor it); events on Enviar (rejected: Phoenix/`chat.log` already have turns; Gradio event `js=` arity is fragile).

### Decision: Matomo site via MCP, ids only in operator env

Search the public origin first; `SitesManager.addSite` only if missing. `excludeUnknownUrls` on. No loopback aliases. `idSite` and tracker origin go in gitignored `.env` / dump-host `.env`. `deploy.sh` does not overwrite an existing remote `.env`.

Tracked files MUST NOT contain the public hostname (`tests/test_no_private_layout.py`).

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Structured JSON; FastAPI; prompt with last_refresh / to_as_of | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters | Recommender |
| Vector search; parent = get_section | Second index |

### Decision: Slip order

1. Idempotent Matomo site
2. `matomo_snippet` + `observatory_head` + `mount_ui` settings
3. Env examples + README How to run
4. Unit tests

Never cut: fail-open, no PII, no mail-link tracking, no live Matomo in default pytest. Deontic scan stays slip-first (not this change).

## Risks / Trade-offs

- [Laptop `.env` keys fire during live Gherkin] → loopback gate unless `?matomo=1`.
- [Invalid URL interpolated into HTML] → sanitize; omit snippet.
- [Public hostname in git] → empty examples; private-layout test.
- [Deploy does not update existing remote `.env`] → operator append + `systemctl restart bcra-rag`.
- [DNT visitors never appear] → accepted; matches sibling sites.
- [Ad blockers drop `matomo.js`] → accepted; same as other sites on this collector.
- [Snippet lives in `window.gradio_config.head` JSON, not a top-level `<script src>`] → expected Gradio 6; verify with a real browser, not curl-only.

## Migration Plan

No dump or index migration. Create/reuse the Matomo site, set `MATOMO_URL` and `MATOMO_SITE_ID` on the dump host, restart `bcra-rag`. Rollback: revert; empty keys inject nothing.

## Open Questions

None.
