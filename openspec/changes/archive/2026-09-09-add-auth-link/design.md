## Context

See proposal.md Why and the delta specs. Sibling changes `add-authentication` and `harden-authentication` own `bcra_rag.auth`, the session gate in `handle_turn`, and same-screen login. This change adds a login URL in the same OTP mail, shortens the session, and caps language-model turns. It does not add a sixth RAG port.

Unchanged architecture:

- **Ports:** Catalog, Extractor, Index, Llm, SessionStore. Those five stay five. Mailer stays inside `bcra_rag.auth`.
- **Composition:** `build_ingest` / `build_app`; `handle_turn` is still the single query gate.
- **Ingest/refresh pipeline, router, chunking A/B:** untouched.
- **Session memory:** in-process last-six turns, still HMAC-scoped by email inside `handle_turn`.
- **Host-side refresh:** systemd oneshots + cron.d. uvicorn remains `127.0.0.1:8000` without `--proxy-headers`.
- **IBM 1–4 take/leave and slip order:** unchanged (citation honesty → freeze dates → deontic scan later). Deontic scan stays slip-first.

Constraints: Python 3.11+ via uv; FastAPI; Gradio 6.x mounted at `/`; one worker; no Redis.

## Goals / Non-Goals

**Goals:**

- High-entropy login token in the OTP mail (5 min, hashed, same slot as the 6-digit code).
- Hybrid consume: token-path GET never sets a session; washed GET auto-logs in only with bound intent + top-level navigation; otherwise confirm POST.
- Multipart mail (plain + observatory-look HTML, email-safe inline CSS).
- Session Max-Age 86400.
- Daily chat caps 30/email and 100/process with structured logs.
- Tests for new and updated behavior; `src` coverage >= 80%.

**Non-Goals:**

- Redis / cookie denylist / CAPTCHA / uvicorn access-log redaction / `--proxy-headers`.
- A second Gradio UI. Confirm HTML is a FastAPI interstitial.
- Opening `AUTH_ALLOWED_EMAILS=*`.
- CI-blocking live magic-link click or a paid L1 run.

## Decisions

### Decision: token-path GET only washes

`GET /auth/link/{token}` never calls `sign_session`. It sets HttpOnly `auth_link=<token>` (`Path=/auth/link`, `SameSite=Lax`, `Max-Age=otp_ttl_s`, `Secure` via `cookie_secure`), then 302 `Location: /auth/link`. Headers on `/auth/link*`: `Cache-Control: no-store`, `Pragma: no-cache`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, CSP `default-src 'none'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; style-src 'unsafe-inline'`. Do not log the raw token or the `Set-Cookie` value.

`_reject_bad_origin` applies to `POST /auth/request`, `POST /auth/verify`, and `POST /auth/link` only. **GET `/auth/link` and GET `/auth/link/{token}` skip it** (mail `Referer` is foreign). Register these routes on the parent FastAPI app the same way as today’s `/auth/request` (before `gr.mount_gradio_app(..., path="/")`). Verify against `build_app`, not the router alone, so Gradio cannot steal the GET.

Join the mail URL as `public_origin.rstrip("/") + "/auth/link/" + token`.

Alternative: authenticate on the token URL — rejected (Referer, history, prefetch, access-log hop all carry a live session).

### Decision: hybrid auto-login only on washed GET

`GET /auth/link` (no token in the path) auto-consumes only when **all** hold: live `auth_link` token, `auth_intent` cookie matches the nonce bound to that token, method GET not HEAD, `Sec-Fetch-Mode: navigate` and `Sec-Fetch-Dest: document`. Missing Sec-Fetch → confirm page (fail closed). Otherwise Spanish confirm: `lang=es`, one `h1`, mailbox visible and in the submit label, native `<form method="post" action="/auth/link">`, token not in HTML. POST uses the `auth_link` cookie, origin-checks when `AUTH_PUBLIC_ORIGIN` is set, 403 must not burn.

Failed consumes (unknown token, origin 403, bad POST) share the existing **verify IP failure / lockout** buckets. They MUST NOT increment `_Otp.fails` on a *different* mailbox and MUST NOT delete another row.

`AuthService.request_otp` returns a small result (`intent_nonce`, optional `login_url`); it does not touch HTTP. `POST /auth/request` in `routes.py` sets `auth_intent=<nonce>` with the same flags as `auth_link`. Store the **raw intent nonce** on the in-memory `_Otp` row (it already lives in the cookie) plus `link_digest`. Lookup link by `HMAC(AUTH_SECRET, token)` (no email in the URL).

**Coalesce:** do not mint a new nonce, do not rotate `link_digest`. Re-set the same `auth_intent` cookie (refresh Max-Age) from the stored nonce so a double Enviar does not break one-tap.

Alternative: always confirm — safer, worse same-browser UX. Alternative: device-bind only — breaks phone-mail / desktop-site, rejected. Alternative: new intent on every `/auth/request` — rejected (coalesce would break auto-login).

### Decision: opaque token, not the 6 digits

`secrets.token_urlsafe(32)`. Store HMAC hex, never the raw token on `_Otp`. URL `{public_origin.rstrip("/")}/auth/link/{token}`. If public origin is empty, omit the URL (OTP-only). Never `request.base_url` / `Host`.

First success (verify OTP **or** consume link) deletes the `_Otp` row. Coalesce of a live secret does not send mail or rotate the token (harden-authentication). Same `RLock` for consume lookup+burn; do not hold it across HTML render or SMTP on GET.

### Decision: multipart mail in `mail_copy.py`

`EmailMessage.set_content(otp_body(...))` then `add_alternative(otp_html_body(...), subtype="html")`. `FakeMailer` records `body` and `html`. HTML: table ~600px, inline `style` + `bgcolor`, hex from observatory (`#04111d`, `#081a2b`, `#f4fbff`, `#b6c9d4`, `#72d6cb`, `#03101c`, `#2a4a55`). Button text `Iniciar sesión`, `rel="noopener noreferrer"`, digits as text, URL repeated as visible text, no `<img>`, no mailbox in HTML (confirm page names it). Escape interpolations. Subject unchanged.

Tests and live IMAP MUST parse `Tu código de acceso es (\d{6})`, not `\b(\d{6})\b` (`token_urlsafe` can include hyphen-bounded digits).

### Decision: session default 24 hours

`AuthSettings.session_days` default `1` (`session_ttl_s == 86400`). Existing cookies keep stamped `exp`. Logout already exists (`#auth-logout`); `demo.load` still hydrates from the session cookie after 302 `/`.

### Decision: chat caps on RAG `Settings`, gated in `handle_turn`

`CHAT_TURNS_PER_EMAIL_DAY=30`, `CHAT_TURNS_PER_PROCESS_DAY=100`. In-process counters keyed by UTC day and `normalize_email`, sitting next to `RateLimiter`. Order in `handle_turn`: session → demo key → skip `/clear` (do not increment; burst limiter may still see clear, as today) → email cap → process cap → burst 20/60s → `AnswerQuery`. Increment when the question is accepted past session/demo, **before** burst, so a later burst 429 still consumed a daily slot (same position as today’s `limiter.allow`). A cap 429 does not increment again. 429 logs `email_cap` / `process_cap` plus 8-char email hash, never raw email. Unauthenticated 401 still happens first and does not increment.

Observatory Enviar on HTTP 429 reuses the existing Spanish copy `Demasiados intentos. Probá más tarde.` (auth JS already does this; chat `_turn` must too).

If `AUTH_ALLOWED_EMAILS=*` (sibling change, not this one) these caps are the spend brake.

Alternative: cap by IP — rejected (NAT vs botnet). Alternative: Redis — forbidden.

### Decision: tests

Default `uv run pytest -q` (fakes). TestClient wash uses `follow_redirects=False`. Auto-login tests send Sec-Fetch headers; a default GET is the scanner case. Wash/confirm GET tests use `build_app` (Gradio mounted) and a mail `Referer`. Coalesce test: second `/auth/request` then auto-login still works. Trailing-slash origin test. Failed-consume test does not burn another mailbox. Update 7-day assertions (`session_days`, `max-age=86400`, rename week test). Coverage >= 80%. Live magic-link click is not CI-blocking; live OTP extractor still updates.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| 1 Ground in dump ids + `last_refresh` / `to_as_of` | Multi-agent / HITL |
| 2 Cite or abstain | LlamaIndex / second index |
| 3 Deterministic finding demotion after generation | Deontic scan as a v1 MUST |
| 4 Visible guardrail log (staff surface) | Filling 1990–97 hole |

Slip order (design only): citation honesty → freeze dates → deontic scan later.

## Risks / Trade-offs

- [First GET still logs the token on uvicorn’s request line] → entropy + 5 min + single-use + wash so later hops are clean; app logs never persist it.
- [Sec-Fetch missing on old browsers] → confirm page, one extra click; OTP still works.
- [Cookies-off cannot POST confirm] → typed OTP remains.
- [HTML mail clients strip backgrounds] → every text cell sets `bgcolor` and color; button is solid teal/dark.
- [In-memory caps reset on restart] → same as OTP send caps; accepted.
- [Process cap 100 can fire before a mailbox hits 30] → intended; both log.
- [Existing 7-day cookies remain until stamped exp] → no secret rotation in this change.
- [Mail Referer vs origin check] → GET `/auth/link*` skips origin; only POSTs are checked.
- [Double Enviar mints a new intent] → coalesce reuses the stored nonce.
- [`AUTH_ALLOWED_EMAILS=*`] → out of this change; 30/100 caps are then load-bearing.
- [Gradio `path="/"` steals GET `/auth/link`] → same mount order as `/auth/request`; TestClient against `build_app`.

## Migration Plan

Deploy the serving process as today. Set `AUTH_PUBLIC_ORIGIN` to the public `https://` origin so mail URLs work and cookies are Secure. New verifies and link consumes get 24h cookies. Chat caps start at 0 after boot. Rollback: previous binary (7-day new sessions, no link, no daily caps). No dump wipe. Git-flow version bump stays after `develop`, not in this change.

## Open Questions

None.
