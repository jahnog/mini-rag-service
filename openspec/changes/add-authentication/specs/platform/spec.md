## ADDED Requirements

### Requirement: Unauthenticated chat is rejected
`POST /chat` and `POST /chat/clear` SHALL require a valid session. Without one they SHALL return HTTP 401, MUST NOT retrieve, MUST NOT call the language model, MUST NOT write chat session memory, and MUST NOT produce invented CAMEX text. An optional shared demo secret, when configured, SHALL still be required in addition to the session (not instead of it). The existing per-client chat rate limit SHALL apply only after the session is accepted.

#### Scenario: Repeated unauthenticated posts do not call the model
- **GIVEN** no session credential
- **WHEN** several chat requests are sent
- **THEN** each response is HTTP 401
- **AND** the language model is not called

#### Scenario: Demo secret is not a substitute for the session
- **GIVEN** a configured demo secret
- **AND** no session credential
- **WHEN** a chat request is sent with that demo secret
- **THEN** the response is HTTP 401
- **AND** the language model is not called

## MODIFIED Requirements

### Requirement: Rate limit
The system SHALL apply a crude per-client rate limit (default 20 chat requests per 60 seconds) and SHALL queue concurrent UI users. Extra requests SHALL be rejected or delayed and MUST NOT each produce a full CAMEX answer. An optional shared demo secret MAY be required when the UI is on a public URL. A local demo MAY leave that secret unset. Client identity for this limit SHALL use the same trusted-proxy rule as authentication (connecting address unless trusted-proxy is on). Unauthenticated requests MUST NOT consume this chat budget (they fail authentication first).

#### Scenario: Repeated requests are limited
- **GIVEN** an authenticated client that exceeds the configured request rate
- **WHEN** further chat requests are sent
- **THEN** those extra requests are rejected or delayed
- **AND** they do not each produce a full CAMEX answer

#### Scenario: Unauthenticated 401 does not eat the chat budget
- **GIVEN** no session credential
- **AND** the chat rate limit is 2 requests per 60 seconds
- **WHEN** three unauthenticated chat requests are sent
- **THEN** each is HTTP 401
- **AND** a later authenticated request is not rejected solely because of those three
