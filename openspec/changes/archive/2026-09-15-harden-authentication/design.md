## Context

See proposal.md Why and the delta specs. Sibling change `add-authentication` introduced `bcra_rag.auth`, the session gate in `handle_turn`, and same-screen login. This change hardens that slice; it does not add a sixth RAG port.

Unchanged architecture:

- **Ports:** Catalog, Extractor, Index, Llm, SessionStore. Those five stay five. Mailer stays inside `bcra_rag.auth`. `SessionStore` still stores last-six chat turns; it does not grow an owner field.
- **Composition:** `build_ingest` / `build_app`; `handle_turn` is still the single query gate.
- **Ingest/refresh pipeline, router, chunking A/B:** untouched.
- **Host-side refresh:** systemd oneshots + cron.d. uvicorn remains `127.0.0.1:8000` without `--proxy-headers`.
- **IBM 1–4 take/leave and slip order:** unchanged (citation honesty → freeze dates → deontic scan later). Deontic scan stays slip-first.

Constraints: Python 3.11+ via uv; FastAPI; Gradio 6.x mounted at `/`; one worker; no Redis.

## Goals / Non-Goals

**Goals:**

- `Secure` session cookies in production without trusting uvicorn’s HTTP scheme alone.
- Coalesce live OTPs; commit digest only after a successful send; SMTP timeout; process-wide lock on request/verify.
- Scope chat memory by authenticated email inside `handle_turn` (public UUID on the wire).
- Origin match on scheme + host + port.
- Logged-out Clear keeps history and shows the Spanish notice.

**Non-Goals:**

- Redis / cookie denylist / `--proxy-headers` / CAPTCHA / itsdangerous rewrite.
- Changing `SessionStore` or `ChatRequest` / `ChatResponse` fields.
- Redacting `thinking` from authenticated `/chat` JSON.

## Decisions

### Decision: `cookie_secure` signals

`cookie_secure(request, settings)` is true if any of:

1. `AUTH_PUBLIC_ORIGIN` scheme is `https`
2. `AUTH_TRUST_PROXY` and first `X-Forwarded-Proto` hop is `https`
3. `Origin` or `Referer` scheme is `https`
4. `request.url.scheme == "https"`

`Set-Cookie` and `delete_cookie` share it. Ignore forwarded proto unless trust-proxy (same rule as XFF). Alternative: uvicorn `--proxy-headers` — rejected; allow-ips mistakes spoof the scheme. Public origin is the operator pin when Origin is stripped.

### Decision: `origin_matches(expected, incoming)`

Parse both URLs. Compare scheme, hostname (lowercase), and port. Treat omitted port as 443 for https and 80 for http. Missing incoming is a mismatch when expected is set. Used by `/auth/request` and `/auth/verify` only.

### Decision: one `RLock` including SMTP

`request_otp` and `verify_otp` take `threading.RLock` for the whole call, including `mailer.send_otp`. `email_from_cookie` / chat do not take it. SMTP timeout (default 10s) bounds wait. Alternative: inflight flag and release during SMTP — more states, easy to return `{ok: true}` before a code exists. Auth volume is tiny; hold the lock.

`request_otp` order under the lock:

1. secret + email validate
2. unexpired OTP → log `sent`, return (no limits, no SMTP)
3. enforce send limits
4. record send attempt
5. `send_otp`
6. success → store HMAC; exception → `AuthUnavailable` (HTTP 503), no digest

### Decision: namespace session ids in `handle_turn`

After `email_from_request`:

- `public_id = session_id or uuid4()`
- store key = `HMAC-SHA256(AUTH_SECRET, f"{email}|{public_id}")`
- pass the store key into `AnswerQuery`
- rewrite `ChatResponse.session_id` back to `public_id`

Do not change `SessionStore`. Alternative: owner field on the port — extra protocol surface for one product concern.

Follow-up leak tests MUST use a message that `_compose_followup` prefixes (`y ese punto?`). A full new question would not copy prior user text even without namespacing.

### Decision: Clear helper

Module-level `apply_clear_result(history, session_id, error)` next to `http_turn_notice`. `_clear` takes chatbot history; on 401 appends `AUTH_NOTICE` and keeps rows; on success returns empty history and `None` session id.

### Decision: tests

Unit tests for `origin_matches` / `cookie_secure`. HTTP TestClient for Set-Cookie flags, 403 origin, 503 mail, cross-mailbox `/chat`. Concurrent threads on `request_otp`. Mock `smtplib.SMTP` for timeout kwarg. No live SMTP. UI tests call `apply_clear_result`, not the nested Gradio closure. README names `AUTH_SMTP_TIMEOUT_S`. Coverage >= 80%.

## Risks / Trade-offs

- [Holding the lock across SMTP] → 10s timeout; chat does not take the lock.
- [Secure from spoofable Origin] → preferring Secure is conservative; public origin is the production pin.
- [HMAC store keys die if AUTH_SECRET rotates] → same as cookies; in-memory chat TTL is 1h.
- [Coalesce extends a live code’s usefulness for 5 min] → stops replace-DoS and double-send; 10/day still caps after expiry.
- [No server-side cookie revoke] → unchanged; HttpOnly + Secure + SameSite.

## Migration Plan

Deploy the serving process as today. Set `AUTH_PUBLIC_ORIGIN` to the public `https://` origin before traffic. Existing session cookies remain valid until expiry; new verifies get `Secure` when HTTPS signals are present. Rollback: previous binary. No dump wipe. Git-flow version bump stays after `develop`, not in this change.

## Open Questions

None.
