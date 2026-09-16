## ADDED Requirements

### Requirement: Chat memory is bound to the authenticated email
Chat turn memory SHALL belong to the authenticated email. The public session id on the wire SHALL remain a UUID. A later authenticated client that presents the same session id under a different email MUST NOT retrieve, continue, or send those prior turns to the language model. The same email with the same session id SHALL still resume. Unauthenticated requests still MUST NOT write chat session memory.

#### Scenario: Follow-up does not leak across mailboxes
- **GIVEN** an authenticated session for `ops@example.com` with a prior turn
- **AND** that turn’s session id
- **WHEN** `other@example.com` is authenticated and posts a follow-up with that session id
- **THEN** the language model is not given the prior turn from `ops@example.com`
- **AND** the response is not HTTP 401

#### Scenario: Same mailbox still follows up
- **GIVEN** an authenticated session for `ops@example.com` with a prior turn
- **WHEN** that mailbox posts a follow-up with the same session id
- **THEN** the language model receives that prior turn
