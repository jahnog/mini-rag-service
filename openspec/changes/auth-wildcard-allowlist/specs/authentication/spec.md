## MODIFIED Requirements

### Requirement: Allowlist
The system SHALL send a one-time secret only to emails on a configured allowlist, compared after normalizing the address (trim, lowercase, collapse a `+tag` in the local part). An empty allowlist SHALL send nothing. When the configured allowlist contains the token `*` (comma-separated entries, trimmed), every well-formed email SHALL be treated as allowlisted and SHALL receive a secret when mail is configured and no send limit is exceeded. Other entries in the same list SHALL NOT restrict that wildcard. Every authenticated email MAY use the end-user layout and MAY switch to the staff layout.

#### Scenario: Empty allowlist sends nothing
- **GIVEN** the allowlist is empty
- **WHEN** a client requests a one-time secret for any well-formed email
- **THEN** no message is sent
- **AND** the response shape matches a successful request

#### Scenario: Plus-tag matches the allowlisted mailbox
- **GIVEN** the allowlist includes `ops@example.com`
- **AND** mail is configured
- **WHEN** a client requests a one-time secret for `ops+staff@example.com`
- **THEN** a message is sent to the requested address
- **AND** that mailbox counts as `ops@example.com` for send limits and allowlist match

#### Scenario: Wildcard allowlist sends to any well-formed email
- **GIVEN** the allowlist contains `*`
- **AND** mail is configured
- **WHEN** a client requests a one-time secret for `stranger@example.com`
- **THEN** a message is sent to `stranger@example.com`
- **AND** the body contains a 6-digit secret
- **AND** the subject does not contain that secret

#### Scenario: Wildcard with other entries still sends
- **GIVEN** the allowlist contains `*` and `ops@example.com`
- **AND** mail is configured
- **WHEN** a client requests a one-time secret for `stranger@example.com`
- **THEN** a message is sent to `stranger@example.com`

#### Scenario: Plus-tag under wildcard still collapses for limits
- **GIVEN** the allowlist contains `*`
- **AND** mail is configured
- **WHEN** a client requests a one-time secret for `ops+staff@example.com`
- **THEN** a message is sent to `ops+staff@example.com`
- **AND** that mailbox counts as `ops@example.com` for send limits
