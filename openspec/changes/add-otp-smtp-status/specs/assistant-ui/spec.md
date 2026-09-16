## ADDED Requirements

### Requirement: Send-code mail-server status
After the user requests a one-time secret from the login row, the assistant interface SHALL show a Spanish status for about two seconds that reports whether that secret was handed to the mail server. A successful request (including an allowlist miss and a request that does not send because a live secret already exists) SHALL use delivered wording. A failed mail-server handoff or a failed request SHALL use not-delivered wording. After that interval the idle Spanish hint SHALL return unless a later login action already replaced the line. Rate-limit, origin, and invalid-email notices SHALL remain until the next auth action. The interface MUST NOT open a second product UI. The status MUST NOT name the mailbox or the digits.

#### Scenario: Successful send shows delivered then idle
- **GIVEN** the interface is shown without a session
- **AND** mail is configured
- **AND** the email is allowlisted
- **WHEN** the user requests a one-time secret
- **THEN** the status reports that the secret was handed to the mail server
- **AND** after about two seconds the idle Spanish hint is shown again
- **AND** the question input remains on the same screen

#### Scenario: Failed send shows not delivered then idle
- **GIVEN** the interface is shown without a session
- **AND** the email is allowlisted
- **AND** mail delivery fails
- **WHEN** the user requests a one-time secret
- **THEN** the status reports that the secret was not handed to the mail server
- **AND** after about two seconds the idle Spanish hint is shown again
- **AND** the status does not name the mailbox or the digits

#### Scenario: Allowlist miss looks like delivered
- **GIVEN** the interface is shown without a session
- **AND** the allowlist does not include the typed email
- **WHEN** the user requests a one-time secret
- **THEN** the status uses the same delivered wording as a successful send

#### Scenario: Too-many-attempts notice stays
- **GIVEN** the interface is shown without a session
- **AND** a send limit applies
- **WHEN** the user requests a one-time secret
- **THEN** a Spanish too-many-attempts notice is shown
- **AND** that notice remains after two seconds

#### Scenario: Verify before the flash ends keeps verify copy
- **GIVEN** the interface is shown without a session
- **AND** the user has just requested a one-time secret
- **WHEN** the user verifies that secret before two seconds have passed
- **THEN** the status reports that the session started
- **AND** it does not return to the idle hint from that send
