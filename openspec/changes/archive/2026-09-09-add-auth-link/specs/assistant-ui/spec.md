## MODIFIED Requirements

### Requirement: Login chrome on the same screen
While the client is not authenticated, the assistant interface SHALL show a login row on the same screen: an email field, a control to send the one-time secret, a 6-digit field, a control to verify, and a status message. Copy SHALL be Spanish. While authenticated, that row SHALL hide the request/verify fields and SHALL show the signed-in email plus a logout control. Login and logout MUST NOT open a second product UI. A short confirm step for a mail login link MAY appear and MUST then return to this same assistant screen with the logout control visible. Logout MUST NOT clear the conversation by itself.

#### Scenario: Logged-out load shows login
- **GIVEN** the interface is shown without a session
- **WHEN** the user looks at the screen
- **THEN** an email field and a send-code control are visible
- **AND** the question input remains on the same screen

#### Scenario: Logged-in load shows logout
- **GIVEN** a valid session for `ops@example.com`
- **WHEN** the interface loads
- **THEN** a logout control is visible
- **AND** the request-code fields are not shown

#### Scenario: Logout returns the login row
- **GIVEN** an authenticated session
- **WHEN** the user logs out
- **THEN** the login row is visible again
- **AND** staff chrome is not shown
- **AND** prior conversation turns remain until Clear

#### Scenario: Mail-link session shows logout on the assistant
- **GIVEN** the client authenticated from a login link as `ops@example.com`
- **WHEN** the assistant screen loads
- **THEN** a logout control is visible
- **AND** the request-code fields are not shown
- **AND** the question input remains on the same screen

## ADDED Requirements

### Requirement: Mail-link confirm stays an interstitial
When a login link needs confirmation, the system SHALL show a Spanish page that names the mailbox, offers a native confirm control that works without page script, and MUST NOT present a second product assistant. After success or failure the user SHALL be able to reach the existing assistant screen. Typed 6-digit login SHALL remain on the observatory.

#### Scenario: Confirm names the mailbox and works without script
- **GIVEN** a valid unused login token for `ops@example.com`
- **AND** the client did not request that secret in this browser
- **WHEN** the client opens the login URL
- **THEN** the page is in Spanish
- **AND** it names `ops@example.com`
- **AND** a form posts without requiring page script
- **AND** the observatory question input is not replaced by a second product UI

#### Scenario: Typed code remains available
- **GIVEN** the assistant is shown without a session
- **WHEN** the user looks at the login row
- **THEN** the 6-digit field and verify control are still on that screen

### Requirement: Limit notice on the assistant
When Enviar is refused because a send or chat limit was exceeded, the assistant interface SHALL show a Spanish notice that there were too many attempts, MUST NOT produce a CAMEX answer, and MUST NOT call the language model.

#### Scenario: Daily cap shows Spanish notice
- **GIVEN** an authenticated session that has reached the email language-model cap
- **WHEN** the user sends a question
- **THEN** the language model is not called
- **AND** a Spanish notice tells them there were too many attempts
