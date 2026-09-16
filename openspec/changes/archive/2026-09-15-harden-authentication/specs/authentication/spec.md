## MODIFIED Requirements

### Requirement: Request a one-time secret
The system SHALL accept a request that names an email and SHALL send a cryptographically random 6-digit one-time secret to that email when the email is on the configured allowlist, mail is configured, and no send limit is exceeded. The secret SHALL expire 5 minutes after it is issued. When that mailbox already has an unexpired unused secret, a later request SHALL return the same success shape, MUST NOT send a message, MUST NOT consume send limits, and MUST leave the existing secret valid. The one-time secret SHALL appear in the message body and MUST NOT appear in the message subject. The system SHALL store only a keyed hash of the secret, never the digits themselves. When the email is not on the allowlist, or mail is not configured, the system MUST NOT send a message and MUST still return the same success shape as a send (no oracle). Malformed emails (missing `@`, whitespace, header-injection characters, unreasonable length) SHALL be rejected without sending. Two overlapping requests for the same mailbox MUST result in at most one message.

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

#### Scenario: Live secret is not rotated
- **GIVEN** an unused one-time secret for `ops@example.com` issued 10 seconds ago
- **WHEN** a client requests another secret for `ops@example.com`
- **THEN** no message is sent
- **AND** the response shape matches a successful request
- **AND** the original secret still authenticates

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

### Requirement: Verify the one-time secret
Submitting the same email and the current unexpired 6-digit secret SHALL authenticate that email for 7 days. The secret SHALL be single-use. Comparison SHALL NOT leak the secret through timing of a digit-by-digit mismatch. Five failed attempts for a given secret SHALL burn it. An expired, burned, or unknown secret SHALL fail with the same generic error. Success SHALL set an HTTP-only session credential the browser sends on later requests. The credential MUST NOT be readable from page script. The credential SHALL be marked Secure when the public origin is HTTPS, when a trusted forwarded proto is HTTPS, when the request Origin or Referer is HTTPS, or when the request URL is HTTPS. Logout SHALL forget the credential with the same Secure flag. A local HTTP demo without those HTTPS signals SHALL omit Secure.

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

### Requirement: Send and verify limits
The system SHALL refuse to send or verify without revealing which bucket fired, using HTTP 429 when a limit applies, and MUST NOT send mail on a refused send. A coalesced request that does not send MUST NOT consume send limits. A send attempt that fails to deliver MUST still consume send limits. Defaults:

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
- **AND** that secret has expired
- **WHEN** a client requests another secret for `ops@example.com`
- **THEN** no message is sent
- **AND** the response is HTTP 429

#### Scenario: Failed send still consumes the minute budget
- **GIVEN** mail is configured but delivery fails
- **WHEN** a client requests a one-time secret for an allowlisted email
- **THEN** a second request for that email within a minute is HTTP 429
- **AND** no one-time secret authenticates from the failed send

### Requirement: Origin check
When a public origin is configured, state-changing authentication requests whose `Origin` or `Referer` scheme, hostname, and port do not match that origin SHALL be rejected without sending mail and without authenticating. Default HTTPS port 443 and default HTTP port 80 SHALL match an omitted port. When the public origin is unset, that check SHALL NOT apply (local demo).

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

## ADDED Requirements

### Requirement: Mail send fails closed
When mail delivery fails or exceeds the configured send timeout (default 10 seconds), the system SHALL NOT install a one-time secret, SHALL NOT authenticate, and SHALL fail closed with HTTP 503 on authentication endpoints. The error MUST NOT name the mailbox or the digits. A later successful send after the per-email wait MAY issue a new secret.

#### Scenario: Failed delivery does not authenticate
- **GIVEN** an allowlisted email
- **AND** mail delivery fails
- **WHEN** a client requests a one-time secret
- **THEN** the response is HTTP 503
- **AND** no one-time secret for that request authenticates
- **AND** the response does not contain the mailbox or digits
