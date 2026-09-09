## Context

See proposal.md Why and the delta specs under `specs/` for the session gate, OTP, limits, and Usuario-default observatory.

Product runtime already exists. Unchanged architecture (restated so this design satisfies the constitution):

- **Ports:** Catalog, Extractor, Index (owns embeddings), Llm, SessionStore. Those **five stay five**. Do not add `Mailer` (or anything auth) to `bcra_rag.ports`. `LlmPort.complete(prompt, *, on_thinking=None) -> LlmDraft` stays the only language-model method. `SessionStore` stays chat turns (last six messages); do not store OTP or auth cookies there.
- **Composition:** `build_ingest` / `build_app`; no DI container. `create_fastapi` still builds Blocks and calls `mount_ui`. `build_app` constructs the auth vertical (`build_auth`) and mounts it; chat/UI receive only a session-check facade.
- **Authentication vertical:** new package `bcra_rag.auth` owns settings, mail port+adapters, OTP/limits/cookie service, and `/auth` routes. RAG code does not implement those.
- **Ingest/refresh pipeline:** catalog → polite fetch → classify → extract → chunk A/B → index upsert → MANIFEST checkpoint. Untouched.
- **Router / chunking / session:** aliases; named Com. A `get_section` vs vigente (TO ∪ later A’s); serving uses structured chunker B on TO + clean A’s and fixed A otherwise; in-process chat session, one worker, `/clear`. Untouched except: no `SessionStore` write until the request is authenticated.
- **Host-side refresh:** systemd oneshots + cron.d on the dump host (not GitHub Actions).

Constraints: Python 3.11+ via uv; pydantic v2; FastAPI; Gradio **6.x** mounted on FastAPI at `/` (`gr.mount_gradio_app`), not `launch()` and not Gradio `auth=`. No Redis. Observatory CSS is hatch force-included. Serving is one worker (in-memory OTP/counters die on restart; signed cookies do not).

## Goals / Non-Goals

**Goals:**

- A new vertical module `bcra_rag.auth` (not a sixth RAG port, not logic sprinkled through `api/` / `adapters/` / `use_cases/`).
- Email 6-digit OTP (5 min), signed HttpOnly cookie (7 days), allowlist, the limit table in the spec.
- **401 on `POST /chat`, `POST /chat/clear`, and Gradio `_turn` / `_clear`** before limiter, retrieval, and LLM.
- Default observatory layout Usuario; Staff only with a valid cookie; login row on the same screen.
- Unit tests; Gherkin authenticates first; `src` coverage >= 80%.

**Non-Goals:**

- OAuth, passwords, WebAuthn, TOTP, Gradio `auth=`, second UI, Redis, SQLite OTP store, CAPTCHA, two-role allowlists.
- A sixth RAG port (`Mailer` on `bcra_rag.ports`). Mail stays inside `bcra_rag.auth`.
- Changing `ChatRequest` / `ChatResponse` fields, canned prompts, ingest, or package version.
- Next.js, LlamaIndex, Banxico, 1990–97 hole, GitHub-hosted vector index.

## Decisions

### Decision: new vertical module `bcra_rag.auth`

Authentication is a sibling of the RAG hexagon, not a sixth port on it. One package owns the slice:

```
src/bcra_rag/auth/
  __init__.py      # public facade: build_auth, mount_auth, email_from_request, AuthModule
  settings.py      # AuthSettings, env prefix AUTH_ (not dumped onto RAG Settings)
  ports.py         # Mailer Protocol — lives here, not in bcra_rag.ports
  smtp.py          # SmtpMailer (stdlib smtplib, STARTTLS)
  fake.py          # FakeMailer (records to, subject, body)
  service.py       # OTP, limits, allowlist, signed cookie
  routes.py        # APIRouter: /auth/request|verify|logout|me
  cookies.py       # Set-Cookie / clear helpers
```

Public facade (what RAG may import):

```python
@dataclass
class AuthModule:
    settings: AuthSettings
    service: AuthService
    mailer: Mailer

def build_auth(*, settings: AuthSettings | None = None, mailer: Mailer | None = None) -> AuthModule: ...
def mount_auth(api: FastAPI, auth: AuthModule) -> None: ...
def email_from_request(auth: AuthModule, request: Request) -> str | None: ...
```

`build_app` calls `build_auth()` (tests pass `FakeMailer` + `AuthSettings`) and `mount_auth`. `handle_turn` / Gradio call `email_from_request` only — they MUST NOT hash OTP, sign cookies, or send mail.

`AuthSettings` is its own `BaseSettings` with `env_prefix="AUTH_"` (`SECRET`, `ALLOWED_EMAILS`, `COOKIE_NAME`, `SESSION_DAYS`, `OTP_TTL_S`, `OTP_DIGITS`, `TRUST_PROXY`, `PUBLIC_ORIGIN`, `SMTP_*`, limit fields). Root `bcra_rag.settings.Settings` stays RAG-only. `AUTH_TRUST_PROXY` is read from `AuthSettings` and passed into `client_id_for` at composition.

`bcra_rag.ports.__all__` remains the five RAG ports. A unit test asserts that.

OTP map and send counters live on `AuthService` (same in-process pattern as `RateLimiter`). Chat `SessionStore` is not reused.

Alternatives: sixth RAG `Mailer` port (pollutes the CAMEX hexagon); stuffing OTP into `SessionStore` (mixes 1h chat TTL with 7d identity); auth routes inlined in `api/routes.py` (not a vertical). Redis is still forbidden.

### Decision: signed cookie is the credential

Cookie name `session` (`AuthSettings.cookie_name` / `AUTH_COOKIE_NAME`). Payload: normalized email + exp + nonce, HMAC-SHA256 via Starlette/itsdangerous (already transitive) and `AUTH_SECRET` (≥32 chars). Flags: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age=604800`, `Secure` when the request is HTTPS. Not `__Host-` so local HTTP works.

Gradio events cannot set cookies reliably. The auth module’s router owns `Set-Cookie`:

- `POST /auth/request` `{email}`
- `POST /auth/verify` `{email, code}`
- `POST /auth/logout`
- `GET /auth/me` → `{authenticated, email?}` (`email` only when authenticated; unauthenticated is 200 not 401)

Observatory buttons `fetch` those URLs with `credentials: "same-origin"`, then a Python handler with `gr.Request` reads the cookie and updates widgets.

Missing/short `AUTH_SECRET`: `/auth/*` → 503; `/chat` → 401. No anonymous LLM spend if auth is misconfigured.

Alternatives: `gr.BrowserState` (readable by JS); server-side session table (needs Redis/SQLite and does not survive the “no Redis” rule as well as a signed cookie).

### Decision: one allowlist, fail closed

`AUTH_ALLOWED_EMAILS` comma-separated. Empty = send nothing, generic success. Normalize: strip, lowercase, drop `+tag` in the local part for allowlist **and** limit buckets. Send the message to the requested address (not the collapsed one) so the user still sees the mail.

Every authenticated user may open Staff. Two lists would be a second product.

### Decision: `handle_turn` is the single query gate

`handle_turn` (used by `POST /chat`, `POST /chat/clear`, and Gradio `_turn` / `_clear`) calls `email_from_request` **first**. Order:

1. `email_from_request` → else HTTP 401 `authentication required` (no `SessionStore` write)
2. existing `DEMO_API_KEY` check (extra gate)
3. existing chat `RateLimiter`
4. existing k-cap / `AnswerQuery`

Gradio 401 surface: reuse the Spanish notice path (`Solicitud rechazada.` / new copy `Tenés que ingresar con tu email.`). Do not call `on_thinking`.

`client_id_for` gains `trusted_proxy: bool` from `AuthSettings.trust_proxy` (`AUTH_TRUST_PROXY`, default false). False → `request.client.host`. True → first `X-Forwarded-For` hop. Chat limiter and auth limits share this helper so XFF cannot be spoofed on a naked bind.

### Decision: default Blocks tree is the safe tree

`build_blocks` defaults (process-global first paint):

- Vista value `LAYOUT_USER`
- `#observatory-freeze` and `#observatory-side` `visible=False`
- shell class `layout-user`
- `#auth-login` visible
- `apply_layout(choice, authenticated)` — Staff chrome only if `authenticated and choice == LAYOUT_STAFF`

`demo.load` hydrates logout/email from the cookie; it does **not** auto-switch to Staff.

Login row `#auth-login` pinned Spanish copy:

- email label `Correo`, send `Enviar código`, code `Código`, verify `Verificar`, logout `Cerrar sesión`
- generic status `Si el correo está habilitado, vas a recibir un código.`
- unauthenticated send notice `Tenés que ingresar con tu email.`

OTP email subject (no digits): `Tu código de BCRA Mini-RAG`. Body contains the 6 digits and the 5-minute expiry in Spanish.

### Decision: redact staff outputs unless authenticated Staff

In `_turn`, pass `on_thinking` only when the cookie is valid **and** Vista is Staff. Inspector/trust/cards outputs are empty in Usuario (authenticated or not). HTTP `POST /chat` still returns the full `ChatResponse` (including `thinking`) to an authenticated API client — the JSON contract is unchanged; the observatory is what we redact. Unauthenticated HTTP never reaches `AnswerQuery`.

### Decision: OTP hashing and limits

- `secrets.randbelow(1_000_000)` formatted `06d`
- store `HMAC-SHA256(AUTH_SECRET, f"{email}:{otp}")`, `secrets.compare_digest`
- TTL `AUTH_OTP_TTL_S=300`; new send replaces previous; 5 failures burn
- counters in memory, UTC day keys

Limit defaults match the spec table. All are settings so tests can shrink them.

Allowlist miss: do comparable hashing work, skip SMTP, return 200 `{ok: true}`.

Origin: when `AUTH_PUBLIC_ORIGIN` is set, POST `/auth/request` and `/auth/verify` require `Origin` or `Referer` host to match. Unset → skip (local).

Logs: request id + 8-char hex prefix of `sha256(email)` + outcome. Never OTP, cookie, or raw email.

### Decision: tests inspect helpers, HTTP TestClient, and the Blocks tree

- `bcra_rag.ports.__all__` is still exactly the five RAG ports
- `FakeMailer` + `AuthService` unit tests for hash/expiry/burn/limits/normalization (`tests/test_auth.py` imports `bcra_rag.auth`, not `bcra_rag.ports`)
- `TestClient`: request/verify/logout/me, Set-Cookie flags, 429, origin, 401 `/chat` without cookie, 200 `/chat` with cookie, `/health` 200 without cookie
- `make_client` / BDD fixtures: mint a cookie via FakeMailer + verify (or a test helper that signs a cookie with `AUTH_SECRET`) so existing named-A scenarios stay readable
- Gherkin: add unauthenticated 401; given-ready scenarios authenticate first
- UI: default tree Usuario + `#auth-login`; `apply_layout(Staff, authenticated=False)` hides; `True` shows; existing observatory contracts remain
- Do not make CI depend on Gradio SSR HTML from `GET /`

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| 1 Ground in dump ids + `last_refresh` / `to_as_of` | Multi-agent / HITL |
| 2 Cite or abstain | LlamaIndex / second index |
| 3 Deterministic finding demotion after generation | Deontic scan as v1 MUST |
| 4 Visible guardrail log (staff surface) | Filling 1990–97 hole |

Slip order (design only): citation honesty → freeze dates → deontic scan later. Deontic scan stays slip-first, not this change.

## Risks / Trade-offs

- [Auth logic leaks into `api/routes.py` / `handle.py`] → those files import only `email_from_request` / `mount_auth`; OTP/SMTP/cookie signing stay in `bcra_rag.auth`; test `ports.__all__` stays five names.
- [**BREAKING** `/chat`] → fixtures mint a cookie; README documents `/auth/verify`; evals that POST without a cookie fail until updated.
- [Gradio queue bypasses `/chat`] → `_turn` must call the same `handle_turn` auth check.
- [Process-global Blocks defaults] → default tree is Usuario + login visible.
- [In-memory daily limits reset on restart] → accept; 200/day cap after boot; SQLite later if needed.
- [7-day cookie theft = 7 days of LLM spend] → HttpOnly + HTTPS + SameSite; no server-side revoke; document it.
- [Allowlist in env is world-readable to the service user] → same as other secrets.
- [6-digit space is 1e6] → 5-try burn + per-email verify throttle.
- [Generic 200 on allowlist miss] → attackers cannot enumerate; they can still hit send limits on guessed addresses.
- [Staff fields still in authenticated `/chat` JSON] → accepted; observatory redacts Usuario; gating JSON fields would change the HTTP contract.

## Migration Plan

Deploy the serving process (one worker) as today. No dump wipe, no index rebuild. Set `AUTH_SECRET` (≥32), `AUTH_ALLOWED_EMAILS`, SMTP, and `AUTH_PUBLIC_ORIGIN` on the dump host before traffic. Existing clients of `/chat` need a session cookie. Rollback: previous binary (chat public again). Git-flow version bump happens after this change is on `develop`, not in this change.

## Open Questions

None. Allowlist, SMTP, 401-on-chat, Usuario default, and one-role-after-login are pinned above.
