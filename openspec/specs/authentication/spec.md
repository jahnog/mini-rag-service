# authentication Specification

## Purpose
TBD — Update Purpose after archive. Authentication proves mailbox control with a one-time secret or a mail login link.

## Requirements

### Requirement: Request a one-time secret
The system SHALL accept a request that names an email and SHALL send a cryptographically random 6-digit one-time secret to that email when the email is on the configured allowlist, mail is configured, and no send limit is exceeded. The secret SHALL expire 5 minutes after it is issued. When that mailbox already has an unexpired unused secret, a later request SHALL return the same success shape, MUST NOT send a message, MUST NOT consume send limits, and MUST leave the existing secret, any unused login token, and the login-intent binding for the requesting browser valid. The one-time secret SHALL appear in the plaintext body and, when an HTML body is sent, in that HTML body, and MUST NOT appear in the message subject. When a public origin is configured, the same message SHALL also include a login URL under that origin (trailing slash on the origin omitted) whose path carries a high-entropy login token, never the 6-digit secret and never the mailbox. The system SHALL store only keyed hashes of the 6-digit secret and of the login token, never the digits or the token itself. The login token SHALL expire when the 6-digit secret expires. When the public origin is unset, the message MUST NOT include a login URL. The message SHALL be sent as a plaintext part and an HTML part that carry the same facts (code, expiry, ignore line, and the URL when present). When the email is not on the allowlist, or mail is not configured, the system MUST NOT send a message and MUST still return the same success shape as a send (no oracle). Malformed emails (missing `@`, whitespace, header-injection characters, unreasonable length) SHALL be rejected without sending. Two overlapping requests for the same mailbox MUST result in at most one message.

#### Scenario: Allowlisted email receives a 6-digit secret
- **GIVEN** an allowlist that includes `ops@example.com`
- **AND** mail is configured
- **WHEN** a client requests a one-time secret for `ops@example.com`
- **THEN** a message is sent to `ops@example.com`
- **AND** the plaintext body contains a 6-digit secret
- **AND** the HTML body contains a 6-digit secret
- **AND** the subject does not contain that secret

#### Scenario: Allowlist miss looks like success
- **GIVEN** an allowlist that does not include `stranger@example.com`
- **WHEN** a client requests a one-time secret for `stranger@example.com`
- **THEN** no message is sent
- **AND** the response shape matches a successful request

#### Scenario: Live secret is not rotated
- **GIVEN** the public origin is `https://rag.example`
- **AND** an unused one-time secret and login token for `ops@example.com` issued 10 seconds ago from this browser
- **WHEN** the same client requests another secret for `ops@example.com`
- **THEN** no message is sent
- **AND** the response shape matches a successful request
- **AND** the original secret still authenticates
- **AND** the original login token still authenticates until it expires or is used
- **AND** a later top-level consume from that browser still authenticates without a new intent

#### Scenario: Expired secret can be replaced
- **GIVEN** a one-time secret for `ops@example.com` issued 6 minutes ago
- **WHEN** a client requests a new secret for `ops@example.com`
- **THEN** a message is sent
- **AND** the expired secret does not authenticate
- **AND** the new secret authenticates until it expires

#### Scenario: Overlapping requests send at most one message
- **GIVEN** an allowlist that includes `ops@example.com`
- **AND** mail is configured
- **WHEN** two clients request a one-time secret for `ops@example.com` at the same time
- **THEN** at most one message is sent
- **AND** that secret authenticates

#### Scenario: Public origin adds a login URL
- **GIVEN** an allowlist that includes `ops@example.com`
- **AND** mail is configured
- **AND** the public origin is `https://rag.example`
- **WHEN** a client requests a one-time secret for `ops@example.com`
- **THEN** the plaintext body contains a 6-digit secret and a URL that starts with `https://rag.example/auth/link/`
- **AND** the HTML body contains that secret and that URL
- **AND** the subject contains neither the secret nor the token
- **AND** the URL does not contain the 6-digit secret
- **AND** the URL does not contain `ops@example.com`
- **AND** the URL does not contain `https://rag.example//`

#### Scenario: Trailing slash on public origin does not double
- **GIVEN** an allowlist that includes `ops@example.com`
- **AND** mail is configured
- **AND** the public origin is `https://rag.example/`
- **WHEN** a client requests a one-time secret for `ops@example.com`
- **THEN** the login URL contains `https://rag.example/auth/link/`
- **AND** the login URL does not contain `https://rag.example//`

#### Scenario: Unset public origin omits the login URL
- **GIVEN** an allowlist that includes `ops@example.com`
- **AND** mail is configured
- **AND** the public origin is unset
- **WHEN** a client requests a one-time secret for `ops@example.com`
- **THEN** a message is sent
- **AND** the plaintext body contains a 6-digit secret
- **AND** neither the plaintext body nor the HTML body contains a login URL

### Requirement: Verify the one-time secret
Submitting the same email and the current unexpired 6-digit secret SHALL authenticate that email for 24 hours. The secret SHALL be single-use. Using the login token SHALL also consume the 6-digit secret, and using the 6-digit secret SHALL consume the login token. Comparison SHALL NOT leak the secret through timing of a digit-by-digit mismatch. Five failed attempts for a given secret SHALL burn it (and its login token). An expired, burned, or unknown secret SHALL fail with the same generic error. Success SHALL set an HTTP-only session credential the browser sends on later requests. The credential MUST NOT be readable from page script. The credential SHALL be marked Secure when the public origin is HTTPS, when a trusted forwarded proto is HTTPS, when the request Origin or Referer is HTTPS, or when the request URL is HTTPS. Logout SHALL forget the credential with the same Secure flag. A local HTTP demo without those HTTPS signals SHALL omit Secure.

#### Scenario: Correct code authenticates for a day
- **GIVEN** a one-time secret issued 1 minute ago for `ops@example.com`
- **WHEN** the client submits that email and that secret
- **THEN** the client is authenticated as `ops@example.com`
- **AND** a later chat request within 24 hours is authenticated without a new secret

#### Scenario: Session ends after a day
- **GIVEN** a client authenticated 24 hours ago from a one-time secret
- **WHEN** a later chat request is sent
- **THEN** the client is not authenticated

#### Scenario: Expired secret fails
- **GIVEN** a one-time secret issued 6 minutes ago
- **WHEN** the client submits that secret
- **THEN** the client is not authenticated
- **AND** the error does not distinguish expiry from a wrong secret

#### Scenario: Five failures burn the secret
- **GIVEN** a valid unexpired secret
- **WHEN** the client submits five wrong codes
- **THEN** a sixth attempt with the correct secret does not authenticate
- **AND** the login token for that secret does not authenticate

#### Scenario: Secret is single-use
- **GIVEN** a secret that already authenticated
- **WHEN** the client submits that secret again
- **THEN** the client is not authenticated a second time from that secret

#### Scenario: Code consume burns the login token
- **GIVEN** an unused one-time secret and its login token for `ops@example.com`
- **WHEN** the client authenticates with the 6-digit secret
- **THEN** a later attempt to authenticate with that login token fails

#### Scenario: HTTPS origin sets a Secure credential
- **GIVEN** a valid unexpired secret
- **AND** the public origin is `https://rag.example`
- **WHEN** the client verifies from that origin
- **THEN** the session credential is marked Secure
- **AND** it is not readable from page script

#### Scenario: Local HTTP omits Secure
- **GIVEN** a valid unexpired secret
- **AND** the public origin is unset
- **AND** the request is HTTP without an HTTPS Origin
- **WHEN** the client verifies
- **THEN** the session credential is HTTP-only
- **AND** it is not marked Secure

### Requirement: Logs must not leak secrets
Process logs SHALL NOT persist the one-time secret, the login token, the session credential, or the full email. They MAY persist a request id, a short hash prefix of the email, and an outcome (`sent`, `limited`, `invalid`, `verified`).

#### Scenario: Successful send is logged without digits
- **GIVEN** a one-time secret was sent
- **WHEN** an operator reads the process log
- **THEN** the 6-digit secret is not in that log
- **AND** the login token is not in that log
- **AND** the full email is not in that log

### Requirement: Origin check
When a public origin is configured, POST authentication requests (request a secret, verify a secret, confirm a login link) whose `Origin` or `Referer` scheme, hostname, and port do not match that origin SHALL be rejected without sending mail and without authenticating. Default HTTPS port 443 and default HTTP port 80 SHALL match an omitted port. GET hops on the login-link path MUST NOT be rejected for origin: a mail client Referer or a missing Origin SHALL still wash or show confirm. When the public origin is unset, that check SHALL NOT apply (local demo).

#### Scenario: Mismatched origin is rejected
- **GIVEN** the public origin is `https://rag.example`
- **WHEN** a client requests a one-time secret with Origin `https://evil.example`
- **THEN** no message is sent
- **AND** the client is not authenticated

#### Scenario: HTTP origin is rejected when the public origin is HTTPS
- **GIVEN** the public origin is `https://rag.example`
- **WHEN** a client requests a one-time secret with Origin `http://rag.example`
- **THEN** no message is sent
- **AND** the client is not authenticated

#### Scenario: Default HTTPS port matches
- **GIVEN** the public origin is `https://rag.example`
- **WHEN** a client requests a one-time secret with Origin `https://rag.example:443`
- **THEN** the request is not rejected for origin

#### Scenario: Mail Referer does not block login-link GET
- **GIVEN** the public origin is `https://rag.example`
- **AND** an unused login token for `ops@example.com`
- **WHEN** a client GETs the login URL with Referer `https://mail.google.com`
- **THEN** the request is not rejected for origin
- **AND** the client is not authenticated from that GET alone

### Requirement: Consume a login link
A login URL issued with a one-time secret SHALL authenticate that mailbox for 24 hours when consumed, under the same session-credential rules as a correct 6-digit secret (HTTP-only, not readable from page script, Secure under the same HTTPS signals, 24-hour lifetime, single-use). The hop whose URL still contains the token MUST NOT set a session credential: it MAY store a short-lived HTTP-only cookie scoped to the login-link path and MUST redirect to a token-free login-link URL. A session MAY be set on that token-free GET only when the browser that requested the secret presents the matching intent cookie and the request is a top-level document navigation. Otherwise a valid unused token SHALL show a Spanish confirm page that names the mailbox and authenticates only on a user POST. Missing navigation headers SHALL NOT auto-authenticate (confirm instead). HEAD MUST NOT authenticate and MUST NOT consume the token. An expired, burned, unknown, or already-used token SHALL show the same generic Spanish failure and a token-free link back to the assistant, without setting a session. GET hops on the login-link path MUST NOT require a matching Origin or Referer (mail clients send a foreign Referer). A mismatched origin on the confirm POST SHALL be rejected without authenticating and MUST NOT consume the token. Failed login-link consumes SHALL count toward the same per-client verify-failure limits as a wrong 6-digit secret and MUST NOT burn a different mailbox's unused secret. The confirm page MUST NOT embed the token. Login-link cookies MUST NOT be sent on chat requests. Responses on the login-link path SHALL forbid storing, framing, and leaking a Referer. Process logs MUST NOT persist the login-link cookie value.

#### Scenario: Token-path GET does not authenticate
- **GIVEN** an unused login token for `ops@example.com`
- **WHEN** a client GETs the URL that still contains that token
- **THEN** the client is not authenticated
- **AND** the response redirects to a URL that does not contain the token
- **AND** the token still authenticates on a later allowed consume

#### Scenario: Same-browser top-level navigation signs in
- **GIVEN** a client that requested the one-time secret in this browser
- **AND** an unused login token for `ops@example.com`
- **WHEN** that browser GETs the token-free login-link URL as a top-level document navigation after the redirect
- **THEN** the client is authenticated as `ops@example.com`
- **AND** a later chat request within 24 hours is authenticated without a new secret
- **AND** the 6-digit secret no longer authenticates

#### Scenario: Prefetch does not sign in or burn
- **GIVEN** an unused login token for `ops@example.com`
- **WHEN** a client GETs the login-link URLs without a matching intent cookie and without top-level navigation headers
- **THEN** the client is not authenticated
- **AND** the 6-digit secret still authenticates

#### Scenario: Other browser sees confirm
- **GIVEN** an unused login token for `ops@example.com`
- **AND** a client that did not request that secret
- **WHEN** that client opens the login URL
- **THEN** the client is not authenticated
- **AND** a Spanish confirm page names `ops@example.com`
- **AND** the token is not in that page

#### Scenario: Other browser confirm POST signs in
- **GIVEN** an unused login token for `ops@example.com`
- **AND** a client that did not request that secret is on the confirm page
- **WHEN** that client submits the confirm form
- **THEN** the client is authenticated as `ops@example.com`
- **AND** the 6-digit secret no longer authenticates

#### Scenario: Confirm origin mismatch does not burn
- **GIVEN** an unused login token
- **AND** the public origin is `https://rag.example`
- **WHEN** a client POSTs confirm with Origin `https://evil.example`
- **THEN** the client is not authenticated
- **AND** a later confirm from `https://rag.example` still authenticates

#### Scenario: Failed consume does not burn another mailbox
- **GIVEN** unused one-time secrets for `ops@example.com` and `other@example.com`
- **WHEN** a client POSTs login-link confirm with an unknown token until verify limits apply
- **THEN** `ops@example.com` secret still authenticates
- **AND** `other@example.com` secret still authenticates

#### Scenario: Unknown token is generic
- **GIVEN** a login URL whose token was never issued, already used, or expired
- **WHEN** a client opens that URL
- **THEN** the client is not authenticated
- **AND** the page uses the same Spanish failure copy
- **AND** the page links to the assistant without a token
