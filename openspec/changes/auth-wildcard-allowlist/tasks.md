## 1. authentication

- [ ] 1.1 In `AuthService._request_otp_locked`, treat a parsed allowlist that contains `*` as open (every well-formed email is allowlisted). Empty still sends nothing. Concrete lists without `*` still dummy-succeed on a miss. Do not treat `*` as a mailbox. Mail still required; send/verify limits unchanged. Verify `uv run pytest tests/test_auth.py tests/test_auth_http.py -q`: `allowed_emails="*"` sends a 6-digit secret to `stranger@example.com` (digits not in the subject); `allowed_emails="*,ops@example.com"` still sends to `stranger@example.com`; empty still sends nothing; concrete miss still sends nothing; `ops+staff@example.com` under `*` sends to the requested address and shares the `ops@example.com` minute bucket; existing HTTP allowlist-miss 200 stays green

## 2. docs

- [ ] 2.1 Document `AUTH_ALLOWED_EMAILS=*`: any well-formed mailbox may receive a code; empty still sends nothing. Update `.env.example`, `deploy/env.remote.example`, and the README `## How to run` copy-env paragraph. No new command fence. Verify the How-to-run paragraph names `AUTH_ALLOWED_EMAILS` and `*` and `uv run pytest tests/test_settings.py tests/test_auth.py -q`
- [ ] 2.2 Run `uv run pytest -q` then `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml`. Fix until green with src coverage >= 80%. Do not run a paid L1 eval
