## MODIFIED Requirements

### Requirement: Layout toggle
The assistant interface SHALL provide a management control that switches between a staff layout and an end-user layout without leaving the assistant. The default on load SHALL be the end-user layout, including when a valid session exists. The control SHALL remain visible in both layouts. A visible label next to the control SHALL name both layouts and SHALL state that staff shows the citation inspector, the per-query guardrail log, Calidad L1, and dump freeze dates, and that end-user keeps the question, the answer, send, Clear, and suggested prompts. Switching layout MUST NOT clear the conversation or the session. Selecting the staff layout SHALL apply staff chrome only when the client is authenticated; when the client is not authenticated, freeze chips, the side inspector, the trust log, Calidad L1, and thinking MUST stay hidden and the conversation MUST remain on the end-user layout.

#### Scenario: Default load is staff
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the interface loads
- **THEN** freeze chips, citation inspector chrome, the trust panel, and Calidad L1 are not shown
- **AND** the question input, send, Clear, and suggested prompts are visible
- **AND** the unofficial CAMEX extract wording is visible
- **AND** Calidad L1 is not expanded into the main chat column

#### Scenario: Authenticated reload still defaults to end-user
- **GIVEN** a valid session
- **WHEN** the interface loads
- **THEN** the end-user layout is shown
- **AND** selecting the staff layout reveals freeze chips and the side inspector without a new one-time secret

#### Scenario: Unauthenticated staff selection does not reveal chrome
- **GIVEN** the interface is shown without a session
- **WHEN** the user selects the staff layout
- **THEN** freeze chips, citation inspector chrome, the trust panel, Calidad L1, and thinking are not shown
- **AND** the management control remains visible
- **AND** the interface does not navigate away from the assistant

#### Scenario: Label names both layouts and what changes
- **GIVEN** the interface is shown
- **WHEN** the user looks at the management control
- **THEN** a visible label names the staff layout and the end-user layout
- **AND** the label states that staff shows the citation inspector, the guardrail log, Calidad L1, and dump freeze dates
- **AND** the label states that end-user keeps the question, the answer, send, Clear, and suggested prompts

#### Scenario: Switch to end-user hides debug chrome
- **GIVEN** an authenticated session
- **AND** the interface is in the staff layout
- **WHEN** the user selects the end-user layout
- **THEN** the citation inspector, the guardrail log, Calidad L1, and dump freeze chips are not shown
- **AND** the question input, conversation, send, Clear, and suggested prompts remain
- **AND** the management control and its label remain visible

#### Scenario: Switch back restores staff chrome
- **GIVEN** an authenticated session
- **AND** the interface is in the end-user layout
- **WHEN** the user selects the staff layout
- **THEN** freeze chips, citation inspector chrome, the trust panel, and Calidad L1 are present again
- **AND** the interface does not navigate away from the assistant

#### Scenario: Layout switch keeps the session
- **GIVEN** an authenticated session with prior turns
- **WHEN** the user switches from staff to end-user layout without clearing
- **THEN** those turns remain in the conversation
- **AND** a later question without Clear uses the same session

## ADDED Requirements

### Requirement: Login chrome on the same screen
While the client is not authenticated, the assistant interface SHALL show a login row on the same screen: an email field, a control to send the one-time secret, a 6-digit field, a control to verify, and a status message. Copy SHALL be Spanish. While authenticated, that row SHALL hide the request/verify fields and SHALL show the signed-in email plus a logout control. Login and logout MUST NOT open a second product UI. Logout MUST NOT clear the conversation by itself.

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

### Requirement: Unauthenticated send does not query
The assistant interface SHALL NOT produce a CAMEX answer, silencio clause, thinking trace, or citation inspector update from Enviar, Enter, Clear, or a canned prompt while the client is not authenticated. The user SHALL see a Spanish notice that they must sign in. The language model MUST NOT be called.

#### Scenario: Enviar while logged out
- **GIVEN** the interface is shown without a session
- **WHEN** the user sends a question
- **THEN** the language model is not called
- **AND** a Spanish notice tells them to sign in
- **AND** the citation inspector is not shown

#### Scenario: Clear while logged out
- **GIVEN** the interface is shown without a session
- **WHEN** the user clicks Clear
- **THEN** the language model is not called

### Requirement: Staff payloads stay off the wire in Usuario
When the layout is the end-user layout, or the client is not authenticated, the assistant interface MUST NOT stream a thinking trace into the conversation and MUST NOT fill the citation inspector or the per-query guardrail log for that turn. Authenticated staff layout keeps the existing thinking, inspector, and trust contracts.

#### Scenario: Usuario turn does not stream thinking
- **GIVEN** an authenticated session
- **AND** the interface is in the end-user layout
- **AND** the language-model provider would return a reasoning trace
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the conversation shows the cited answer
- **AND** the thinking region is not shown
- **AND** the citation inspector is not shown
