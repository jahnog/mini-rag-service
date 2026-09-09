## Context

See proposal.md Why and `specs/authentication/spec.md`. Sibling changes `add-authentication` and `harden-authentication` own `bcra_rag.auth`, the session gate in `handle_turn`, and same-screen login. This change only widens allowlist match; it does not add a sixth RAG port.

Current send gate (after validate, coalesce, and send limits): empty `AUTH_ALLOWED_EMAILS` or a normalized address not in the comma-separated set, or a mailer that is not configured, returns the success shape and does not send.

Unchanged architecture:

- **Ports:** Catalog, Extractor, Index, Llm, SessionStore. Those five stay five. Mailer stays inside `bcra_rag.auth`.
- **Composition:** `build_ingest` / `build_app`; `handle_turn` is still the single query gate.
- **Ingest/refresh pipeline, router, chunking A/B, session memory:** untouched.
- **Host-side refresh:** systemd oneshots + cron.d. uvicorn remains `127.0.0.1:8000` without `--proxy-headers`.
- **IBM 1–4 take/leave and slip order:** unchanged (citation honesty → freeze dates → deontic scan later). Deontic scan stays slip-first.

Constraints: Python 3.11+ via uv; FastAPI; Gradio 6.x mounted at `/`; one worker; no Redis.

## Goals / Non-Goals

**Goals:**

- Treat allowlist token `*` as open signup without flipping empty-list fail-closed.
- Keep miss-as-success for concrete lists.
- Document `AUTH_ALLOWED_EMAILS=*` next to the existing auth keys.

**Non-Goals:**

- New env var, domain globs (`*@example.com`), or a second allowlist for Staff.
- Changing OTP, cookies, origin, SMTP timeout, send/verify limits, or observatory copy.
- Changing live Gherkin; those scenarios still assume a concrete list on the running process.

## Decisions

### Decision: token `*` in the existing setting, not a new flag

`AuthSettings.allowlist()` already comma-splits, strips, and lowercases. After that parse, if the set contains `*`, every well-formed email is allowlisted. Empty set still sends nothing. A list without `*` still membership-checks after `normalize_email`. Other tokens beside `*` do not restrict the wildcard.

`*` is not an email: do not run it through `normalize_email` as a mailbox, do not send to it, and do not put it in limit buckets.

Keep the check in `AuthService._request_otp_locked` next to the existing `not allowlist or normalized not in allowlist or not self.mailer.configured` dummy-success path. Mail still required. Limits still fire before send.

Alternatives: empty list means open — rejected; a forgotten env would open chat. `AUTH_OPEN_SIGNUP=true` — two sources of truth. Domain globs — YAGNI.

### Decision: tests and docs only around the match

Unit tests in `tests/test_auth.py` (and HTTP if the client helper is the cheapest way to pin `{ok: true}`):

- `allowed_emails="*"` + `stranger@example.com` → one FakeMailer send, 6-digit body, no digits in subject
- `allowed_emails="*,ops@example.com"` → still sends to `stranger@example.com`
- `allowed_emails=""` still sends nothing
- concrete miss still sends nothing
- `ops+staff@…` under `*` sends to the requested address and shares the `ops@…` minute bucket

Do not change live Gherkin. If the attached process has `*`, the allowlist-miss scenario will send mail; that is an operator config error, not a suite change.

README copy-env paragraph, `.env.example`, and `deploy/env.remote.example` comment that `*` sends to any well-formed mailbox and that empty still sends nothing. No new command fence. Coverage >= 80%.

## Risks / Trade-offs

- [Anyone who verifies can open Staff and spend the language-model budget] → accepted; two-role lists stay a non-goal. Existing send/verify limits and chat rate limit still apply.
- [SMTP host refuses external relay or lands in spam] → app sends `To:` the requested address; operator SPF/DKIM/relay is out of process.
- [Live allowlist-miss fails when the process is on `*`] → document; leave the scenario on a concrete list.
- [`ops@x.com,*` from a typo opens signup] → explicit token is still safer than empty-means-open; comment the sentinel in env examples.

## Migration Plan

Deploy the serving process as today. Set `AUTH_ALLOWED_EMAILS=*` and restart to open signup; leave a concrete list or empty to keep current behavior. Existing session cookies stay valid. Rollback: previous binary, or set a concrete list / empty and restart. No dump wipe. Git-flow version bump stays after `develop`, not in this change.

## Open Questions

None.
