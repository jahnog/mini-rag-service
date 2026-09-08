## 1. authentication

- [x] 1.1 Add `origin_matches` and `cookie_secure` (public origin https, trusted X-Forwarded-Proto, Origin/Referer https, request scheme). Wire `/auth/request` and `/auth/verify` origin checks to scheme+host+port; Set-Cookie and delete_cookie share `cookie_secure`. Verify `uv run pytest tests/test_auth.py tests/test_auth_http.py -q`: default-port 443 matches; http origin vs https public origin is 403 on request and verify; public-origin https sets Secure even on TestClient HTTP; Origin https sets Secure; local HTTP has HttpOnly and not Secure; forwarded proto sets Secure only when trust-proxy; logout delete matches Secure
- [x] 1.2 Hold an RLock for the whole `request_otp` / `verify_otp`. Coalesce unexpired OTP before send limits (no mail, no 429, original code still verifies). Commit HMAC only after successful send. Record the send attempt before SMTP. SMTP failure → `AuthUnavailable`, no digest. `AUTH_SMTP_TIMEOUT_S` default 10 passed into `smtplib.SMTP`. Verify `uv run pytest tests/test_auth.py tests/test_auth_http.py tests/test_settings.py -q`: replace `test_new_request_replaces_previous_secret` with live-OTP coalesce at +0s; after TTL a new code is sent; raising mailer is 503 without digits/email and second request at +0s is 429; concurrent threads send at most one mail; SMTP mock constructed with `timeout=`

## 2. platform

- [x] 2.1 In `handle_turn`, after the session email is known, mint a public UUID when `session_id` is missing, store chat memory under `HMAC-SHA256(AUTH_SECRET, "{email}|{public_id}")`, pass that key into `AnswerQuery`, and rewrite `ChatResponse.session_id` to the public UUID. Verify `uv run pytest tests/test_chat_api.py tests/features/test_chat_bdd.py tests/test_handle.py -q`: `test_session_id_is_not_shared_across_mailboxes` uses `y ese punto?`; B’s last LLM prompt lacks A’s unique token; A’s follow-up still contains it; returned `session_id` parses as UUID; unauthenticated `/chat` remains 401 with no LLM call

## 3. assistant-ui

- [x] 3.1 Extract `apply_clear_result(history, session_id, error)` next to `http_turn_notice`. `_clear` takes chatbot history; 401 keeps turns and appends `Tenés que ingresar con tu email.`; success empties history and session id. Verify `uv run pytest tests/test_ui.py -q`: logged-out clear keeps prior rows and `AUTH_NOTICE`; authenticated clear returns `[]` and `session_id is None`; existing Spanish Enviar notice still passes

## 4. docs

- [x] 4.1 Document `AUTH_SMTP_TIMEOUT_S` in `.env.example`, `deploy/env.remote.example`, and README `## How to run` (public `https://` origin for Secure cookies; `session_id` is not portable across mailboxes). Verify `test_readme_how_to_run_names_auth_vars` includes `AUTH_SMTP_TIMEOUT_S` and `uv run pytest tests/test_settings.py tests/test_auth.py -q`
- [x] 4.2 Run `uv run pytest -q` then `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml`. Fix until green with src coverage >= 80%. Do not run a paid L1 eval
