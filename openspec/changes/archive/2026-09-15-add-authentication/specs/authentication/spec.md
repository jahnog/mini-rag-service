## Purpose

Prove control of an allowlisted email with a short-lived 6-digit one-time secret, keep that person signed in for a week, stop anonymous queries, and limit mail so the one-time secret cannot be used as an open relay.

## ADDED Requirements

### Requirement: Standalone authentication
Authentication SHALL own one-time secrets, session credentials, mail delivery, and send/verify limits as a standalone capability. Retrieval, ingest, chunking, catalog fetch, and the language-model path MUST NOT implement those. Chat SHALL depend on authentication only by requiring a valid session. The assistant interface SHALL depend on it only by asking whether a session is valid (to send a query or to show staff chrome). Ingest and refresh MUST still run when authentication is missing or misconfigured. `GET /health` SHALL still succeed without a session.

#### Scenario: Ingest does not require a session
- **GIVEN** no session credential
- **AND** authentication is misconfigured
- **WHEN** an ingest or refresh job runs
- **THEN** it does not fail for lack of a session

#### Scenario: Chat depends only on session validity
- **GIVEN** an authenticated session
- **AND** Comunicación A 3500 is in the dump
- **WHEN** the client asks what Comunicación A 3500 says
- **THEN** a citation id is `A3500`

#### Scenario: Health stays public when auth is a separate capability
- **GIVEN** no session credential
- **WHEN** the client requests health
- **THEN** the response is HTTP 200

### Requirement: Request a one-time secret
The system SHALL accept a request that names an email and SHALL send a cryptographically random 6-digit one-time secret to that email when the email is on the configured allowlist, mail is configured, and no send limit is exceeded. The secret SHALL expire 5 minutes after it is issued. A later request for the same email SHALL replace any previous unused secret for that email. The one-time secret SHALL appear in the message body and MUST NOT appear in the message subject. The system SHALL store only a keyed hash of the secret, never the digits themselves. When the email is not on the allowlist, or mail is not configured, the system MUST NOT send a message and MUST still return the same success shape as a send (no oracle). Malformed emails (missing `@`, whitespace, header-injection characters, unreasonable length) SHALL be rejected without sending.

#### Scenario: Allowlisted email receives a 6-digit secret
- **GIVEN** an allowlist that includes `ops@example.com`
- **AND** mail is configured
- **WHEN** a client requests a one-time secret for `ops@example.com`
- **THEN** a message is sent to `ops@example.com`
- **AND** the body contains a 6-digit secret
- **AND** the subject does not contain that secret

#### Scenario: Allowlist miss looks like success
- **GIVEN** an allowlist that does not include `stranger@example.com`
- **WHEN** a client requests a one-time secret for `stranger@example.com`
- **THEN** no message is sent
- **AND** the response shape matches a successful request

#### Scenario: New request replaces the previous secret
- **GIVEN** an unused one-time secret for `ops@example.com`
- **WHEN** a later request issues a new secret for `ops@example.com`
- **THEN** the previous secret no longer authenticates
- **AND** the new secret authenticates until it expires

### Requirement: Verify the one-time secret
Submitting the same email and the current unexpired 6-digit secret SHALL authenticate that email for 7 days. The secret SHALL be single-use. Comparison SHALL NOT leak the secret through timing of a digit-by-digit mismatch. Five failed attempts for a given secret SHALL burn it. An expired, burned, or unknown secret SHALL fail with the same generic error. Success SHALL set an HTTP-only session credential the browser sends on later requests. The credential MUST NOT be readable from page script.

#### Scenario: Correct code authenticates for a week
- **GIVEN** a one-time secret issued 1 minute ago for `ops@example.com`
- **WHEN** the client submits that email and that secret
- **THEN** the client is authenticated as `ops@example.com`
- **AND** a later chat request within 7 days is authenticated without a new secret

#### Scenario: Expired secret fails
- **GIVEN** a one-time secret issued 6 minutes ago
- **WHEN** the client submits that secret
- **THEN** the client is not authenticated
- **AND** the error does not distinguish expiry from a wrong secret

#### Scenario: Five failures burn the secret
- **GIVEN** a valid unexpired secret
- **WHEN** the client submits five wrong codes
- **THEN** a sixth attempt with the correct secret does not authenticate

#### Scenario: Secret is single-use
- **GIVEN** a secret that already authenticated
- **WHEN** the client submits that secret again
- **THEN** the client is not authenticated a second time from that secret

### Requirement: Allowlist
The system SHALL send a one-time secret only to emails on a configured allowlist, compared after normalizing the address (trim, lowercase, collapse a `+tag` in the local part). An empty allowlist SHALL send nothing. Every authenticated email MAY use the end-user layout and MAY switch to the staff layout.

#### Scenario: Empty allowlist sends nothing
- **GIVEN** the allowlist is empty
- **WHEN** a client requests a one-time secret for any well-formed email
- **THEN** no message is sent
- **AND** the response shape matches a successful request

#### Scenario: Plus-tag matches the allowlisted mailbox
- **GIVEN** the allowlist includes `ops@example.com`
- **WHEN** a client requests a one-time secret for `ops+staff@example.com`
- **THEN** a message is sent to the requested address
- **AND** that mailbox counts as `ops@example.com` for send limits and allowlist match

### Requirement: Send and verify limits
The system SHALL refuse to send or verify without revealing which bucket fired, using HTTP 429 when a limit applies, and MUST NOT send mail on a refused send. Defaults:

- at most 5 distinct normalized emails per client identity per UTC day
- at most 1 send per normalized email per 60 seconds
- at most 10 sends per normalized email per UTC day
- at most 20 sends per client identity per UTC day
- at most 5 failed verifies per secret, then burn
- at most 15 failed verifies per client identity per hour, then a 15-minute cooldown
- at most 1 verify per normalized email per 2 seconds
- at most 200 sends per process per UTC day

When the wait is known (the 60-second per-email gap), the response SHALL include `Retry-After`. Client identity SHALL be the connecting address unless a trusted-proxy setting is on, in which case it SHALL be the first `X-Forwarded-For` hop. Plus-tags SHALL NOT create extra distinct-email budget.

#### Scenario: Sixth distinct email from one client is refused
- **GIVEN** one client has already requested secrets for 5 distinct emails today
- **WHEN** that client requests a secret for a sixth distinct allowlisted email
- **THEN** no message is sent
- **AND** the response is HTTP 429

#### Scenario: Second send to the same email within a minute is refused
- **GIVEN** a secret was sent to `ops@example.com` 10 seconds ago
- **WHEN** a client requests another secret for `ops@example.com`
- **THEN** no message is sent
- **AND** the response is HTTP 429

### Requirement: Logout and session probe
The system SHALL end the session when the client logs out, and SHALL forget the credential on the browser. Logout MUST NOT clear chat conversation memory by itself. A session probe SHALL report whether the client is authenticated and, when authenticated, the email. The probe MUST NOT require a secret. Unauthenticated probe SHALL succeed with `authenticated` false (not HTTP 401).

#### Scenario: Logout blocks later chat
- **GIVEN** an authenticated client
- **WHEN** the client logs out
- **THEN** a later chat request is unauthenticated
- **AND** HTTP 401 is returned
- **AND** the language model is not called

#### Scenario: Probe without a session
- **GIVEN** no session credential
- **WHEN** the client probes the session
- **THEN** the response indicates not authenticated
- **AND** the status is not HTTP 401

### Requirement: Chat requires a valid session
Every chat turn and every chat-clear SHALL require a valid unexpired session. Without one, the system SHALL respond HTTP 401, MUST NOT retrieve, MUST NOT call the language model, MUST NOT mint or write chat session memory, and MUST NOT produce CAMEX clauses. The assistant interface and the HTTP chat endpoints SHALL share this check. `GET /health` SHALL remain public. Authentication endpoints SHALL remain usable without a session. If the signing secret is missing or shorter than 32 characters, authentication endpoints SHALL fail closed (HTTP 503) and chat SHALL still reject unauthenticated clients.

#### Scenario: Unauthenticated chat is 401
- **GIVEN** no session credential
- **WHEN** the client posts a CAMEX question
- **THEN** the response is HTTP 401
- **AND** the language model is not called
- **AND** retrieval is not performed
- **AND** no chat session id is minted

#### Scenario: Unauthenticated clear is 401
- **GIVEN** no session credential
- **WHEN** the client posts chat-clear
- **THEN** the response is HTTP 401
- **AND** the language model is not called

#### Scenario: Authenticated named Com. A still answers
- **GIVEN** an authenticated session
- **AND** Comunicación A 3500 is in the dump
- **WHEN** the client asks what Comunicación A 3500 says
- **THEN** a citation id is `A3500`

#### Scenario: Health stays public
- **GIVEN** no session credential
- **WHEN** the client requests health
- **THEN** the response is HTTP 200

### Requirement: Logs must not leak secrets
Process logs SHALL NOT persist the one-time secret, the session credential, or the full email. They MAY persist a request id, a short hash prefix of the email, and an outcome (`sent`, `limited`, `invalid`, `verified`).

#### Scenario: Successful send is logged without digits
- **GIVEN** a one-time secret was sent
- **WHEN** an operator reads the process log
- **THEN** the 6-digit secret is not in that log
- **AND** the full email is not in that log

### Requirement: Origin check
When a public origin is configured, state-changing authentication requests whose `Origin` or `Referer` host does not match that origin SHALL be rejected without sending mail and without authenticating. When the public origin is unset, that check SHALL NOT apply (local demo).

#### Scenario: Mismatched origin is rejected
- **GIVEN** the public origin is `https://rag.example`
- **WHEN** a client requests a one-time secret with Origin `https://evil.example`
- **THEN** no message is sent
- **AND** the client is not authenticated
