## ADDED Requirements

### Requirement: First-screen composer
While the client is not authenticated, the assistant interface SHALL keep the question input and send on the same first screen as the login row. On a wide laptop viewport the question input and send MUST be visible without scrolling away from the login row. The interface MUST NOT open a second product UI.

#### Scenario: Wide viewport keeps send with login
- **GIVEN** the interface is shown without a session
- **AND** the interface is shown on a wide laptop viewport
- **WHEN** the user looks at the screen
- **THEN** an email field and a send-code control are visible
- **AND** the question input and send are visible without scrolling

#### Scenario: Narrow viewport still one screen
- **GIVEN** the interface is shown without a session
- **AND** the interface is shown on a narrow viewport
- **WHEN** the user looks at the screen
- **THEN** an email field and a send-code control are visible
- **AND** the question input remains on the same screen

## MODIFIED Requirements

### Requirement: Clear
The interface SHALL provide a Clear control labeled Limpiar and SHALL treat typed `/clear` as the same action. Session id SHALL persist across turns in the same UI session until cleared.

#### Scenario: Clear button
- **GIVEN** a session with prior turns
- **WHEN** the user clicks Clear
- **THEN** the next question does not use those turns

#### Scenario: Clear is labeled Limpiar
- **GIVEN** the interface is shown
- **WHEN** the user looks at the Clear control
- **THEN** the visible label is Limpiar

#### Scenario: Session id persists
- **GIVEN** the interface has minted a session id
- **WHEN** the user sends a second question without clearing
- **THEN** that question uses the same session id

### Requirement: Banner
The assistant interface SHALL show that the corpus is a BCRA CAMEX unofficial extract. The always-visible title SHALL name BCRA CAMEX and that the extract is unofficial. In the staff layout it SHALL also show `to_as_of`, `last_refresh`, last Comunicación id, and document count without opening a settings page. Those dump freeze chips SHALL NOT be shown in the end-user layout.

#### Scenario: Banner after ingest
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the interface loads
- **THEN** those values are visible without opening a settings page
- **AND** the unofficial CAMEX extract wording is visible
- **AND** the visible title names BCRA CAMEX

#### Scenario: Freeze chips hidden in end-user layout
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the user selects the end-user layout
- **THEN** `to_as_of`, `last_refresh`, last Comunicación id, and document count are not shown as freeze chips
- **AND** the unofficial CAMEX extract wording remains visible
- **AND** the visible title still names BCRA CAMEX
