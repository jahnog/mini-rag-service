## ADDED Requirements

### Requirement: Layout toggle
The assistant interface SHALL provide a management control that switches between a staff layout and an end-user layout without leaving the assistant. The default on load SHALL be the staff layout. The control SHALL remain visible in both layouts. A visible label next to the control SHALL name both layouts and SHALL state that staff shows the citation inspector, the per-query guardrail log, Calidad L1, and dump freeze dates, and that end-user keeps the question, the answer, send, Clear, and suggested prompts. Switching layout MUST NOT clear the conversation or the session.

#### Scenario: Default load is staff
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the interface loads
- **THEN** freeze chips, citation inspector chrome, the trust panel, and Calidad L1 are present
- **AND** Calidad L1 is not expanded into the main chat column

#### Scenario: Label names both layouts and what changes
- **GIVEN** the interface is shown
- **WHEN** the user looks at the management control
- **THEN** a visible label names the staff layout and the end-user layout
- **AND** the label states that staff shows the citation inspector, the guardrail log, Calidad L1, and dump freeze dates
- **AND** the label states that end-user keeps the question, the answer, send, Clear, and suggested prompts

#### Scenario: Switch to end-user hides debug chrome
- **GIVEN** the interface is in the staff layout
- **WHEN** the user selects the end-user layout
- **THEN** the citation inspector, the guardrail log, Calidad L1, and dump freeze chips are not shown
- **AND** the question input, conversation, send, Clear, and suggested prompts remain
- **AND** the management control and its label remain visible

#### Scenario: Switch back restores staff chrome
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user selects the staff layout
- **THEN** freeze chips, citation inspector chrome, the trust panel, and Calidad L1 are present again
- **AND** the interface does not navigate away from the assistant

#### Scenario: Layout switch keeps the session
- **GIVEN** a session with prior turns
- **WHEN** the user switches from staff to end-user layout without clearing
- **THEN** those turns remain in the conversation
- **AND** a later question without Clear uses the same session

### Requirement: End-user layout
In the end-user layout the interface SHALL show the question input, the conversation, send, Clear, and the four canned prompts (tipo de cambio de referencia A 3500/A 8359, liquidación de exportaciones, a 2001–2002 superseded-trap, and Com. A 9999). It SHALL hide the citation inspector, the per-query guardrail log, and Calidad L1. It SHALL NOT show dump freeze chips (`to_as_of`, `last_refresh`, last Comunicación id, document count). The footer SHALL still state that the extract is unofficial, not BCRA, not legal advice, and dated as of `last_refresh`. When finding is silencio, an abstain banner SHALL remain visible in the chat column.

#### Scenario: End-user surfaces
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at the screen
- **THEN** the question input, conversation, send, Clear, and suggested prompts are visible
- **AND** the citation inspector, the guardrail log, and Calidad L1 are not shown
- **AND** dump freeze chips are not shown
- **AND** the unofficial-extract footer wording is visible

#### Scenario: Suggested prompts remain in end-user layout
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at suggested prompts
- **THEN** three prompts are answerable from the dump
- **AND** one asks for a comunicación that is not in the dump
- **AND** none is a generic “explain the BCRA”

#### Scenario: Silencio banner stays in the chat column
- **GIVEN** the interface is in the end-user layout
- **AND** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible in the chat column
- **AND** the guardrail log is not shown

#### Scenario: Named Com. A still answers in chat
- **GIVEN** the interface is in the end-user layout
- **AND** Comunicación A 8359 is in the dump
- **WHEN** the user asks what Comunicación A 8359 says
- **THEN** the conversation shows the answer
- **AND** the citation inspector is not shown

#### Scenario: Clear still drops prior turns
- **GIVEN** the interface is in the end-user layout
- **AND** a session with prior turns
- **WHEN** the user clicks Clear
- **THEN** the next question does not use those turns

## MODIFIED Requirements

### Requirement: Banner
The assistant interface SHALL show that the corpus is a BCRA CAMEX unofficial extract. In the staff layout it SHALL also show `to_as_of`, `last_refresh`, last Comunicación id, and document count without opening a settings page. Those dump freeze chips SHALL NOT be shown in the end-user layout.

#### Scenario: Banner after ingest
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the interface loads
- **THEN** those values are visible without opening a settings page
- **AND** the unofficial CAMEX extract wording is visible

#### Scenario: Freeze chips hidden in end-user layout
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the user selects the end-user layout
- **THEN** `to_as_of`, `last_refresh`, last Comunicación id, and document count are not shown as freeze chips
- **AND** the unofficial CAMEX extract wording remains visible

### Requirement: Observatory shell
The assistant interface SHALL be one screen with a topbar, a dominant chat stage, and a footer. In the staff layout it SHALL also show a side inspector. The topbar SHALL show that the corpus is a BCRA CAMEX unofficial extract. In the staff layout the topbar SHALL also show `to_as_of`, `last_refresh`, last Comunicación id, and document count as chips without opening a settings page. The chat stage SHALL hold the conversation, the question input, suggested prompts, send, Clear, and the abstain banner when it applies. In the staff layout the side inspector SHALL hold citation cards, the this-query trust log, and the Calidad L1 section. The end-user layout SHALL NOT show the side inspector. The footer SHALL state that the extract is unofficial, not BCRA, not legal advice, and dated as of `last_refresh`. When the side inspector is visible, on a wide viewport the chat stage SHALL sit to the left of the inspector, and on a narrow viewport the inspector SHALL sit below the chat stage.

#### Scenario: Freeze chips on load
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464, and a document count
- **WHEN** the interface loads
- **THEN** the topbar shows those values as chips
- **AND** the unofficial CAMEX extract wording is visible
- **AND** no settings page is required

#### Scenario: Wide layout keeps chat dominant
- **GIVEN** the staff layout
- **AND** the interface is shown on a wide viewport
- **WHEN** the user looks at the screen
- **THEN** the chat stage is on the left
- **AND** the inspector is on the right

#### Scenario: Narrow layout stacks the inspector
- **GIVEN** the staff layout
- **AND** the interface is shown on a narrow viewport
- **WHEN** the user looks at the screen
- **THEN** the inspector sits below the chat stage
- **AND** chat, citations, and trust remain on the same screen

#### Scenario: Silencio banner stays in the chat stage
- **GIVEN** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible in the chat stage

#### Scenario: Clear still drops prior turns
- **GIVEN** a session with prior turns
- **WHEN** the user clicks Clear
- **THEN** the next question does not use those turns

#### Scenario: End-user layout hides the side inspector
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at the screen
- **THEN** the side inspector is not shown
- **AND** the chat stage, footer, and management control remain visible

### Requirement: Dark observatory chrome
The assistant interface SHALL use a dark background, glass panels, kicker labels, and pill badges on that one screen. Suggested prompts SHALL appear as pills whose text is the existing canned mix (tipo de cambio de referencia A 3500/A 8359, liquidación de exportaciones, a 2001–2002 superseded-trap, and Com. A 9999). Chat and prompts MUST remain usable without opening a second page. In the staff layout, citations and trust MUST remain usable on that same screen.

#### Scenario: Suggested prompts remain pills on the stage
- **GIVEN** the interface is shown
- **WHEN** the user looks at suggested prompts
- **THEN** they appear as pills on the chat stage
- **AND** three prompts are answerable from the dump
- **AND** one asks for a comunicación that is not in the dump
- **AND** none is a generic “explain the BCRA”

#### Scenario: One screen remains usable
- **GIVEN** the staff layout
- **WHEN** the user asks a named Com. A that is in the dump
- **THEN** the answer, citation cards, and trust log are on the same screen
- **AND** the interface does not open a second product UI

#### Scenario: End-user layout stays one screen
- **GIVEN** the end-user layout
- **WHEN** the user asks a named Com. A that is in the dump
- **THEN** the answer is on the same screen as the question input
- **AND** the interface does not open a second product UI

### Requirement: Citation inspector
In the staff layout the interface SHALL show citation cards as the visible inspector, with Comunicación id, fecha, punto when known, a short snippet, a copy-id action, and the official bcra.gob.ar PDF URL. A raw structured dump MUST NOT be the primary inspector surface. Clicking a card SHALL update the inspector, not navigate away. Copy-id SHALL place the dump document id on the clipboard (for example A8359), matching the citation id. The end-user layout SHALL NOT show that inspector.

#### Scenario: Citation card
- **GIVEN** the staff layout
- **AND** an answer that cites A 8359
- **WHEN** the user inspects citations
- **THEN** they see A 8359, its date, a snippet, and a bcra.gob.ar link
- **AND** the visible inspector is the citation cards, not a raw structured dump

#### Scenario: Copy id
- **GIVEN** the staff layout
- **AND** a citation card for A 8359
- **WHEN** the user uses copy-id
- **THEN** the dump id A8359 is placed on the clipboard

#### Scenario: Click stays in inspector
- **GIVEN** the staff layout
- **AND** an answer that cites A 8359
- **WHEN** the user clicks that citation card
- **THEN** the inspector updates to A 8359
- **AND** the interface does not navigate away from the assistant

#### Scenario: End-user layout hides the inspector
- **GIVEN** an answer that cites A 8359
- **WHEN** the user selects the end-user layout
- **THEN** citation cards, copy-id, and the inspector are not shown

### Requirement: Trust panel and abstain banner
In the staff layout the interface SHALL show the per-query guardrail log as pass, warn, or block chips. In both layouts the interface SHALL show an abstain banner in the chat stage when finding is silencio. The end-user layout SHALL NOT show the guardrail log.

#### Scenario: Silencio banner
- **GIVEN** the staff layout
- **AND** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible in the chat stage
- **AND** the named guardrail appears in the panel as a chip

#### Scenario: In-corpus trust panel
- **GIVEN** the staff layout
- **AND** an in-corpus answer with all v1 guardrails passing
- **WHEN** the answer is rendered
- **THEN** the trust panel shows those rules as pass chips

#### Scenario: End-user layout hides the trust log
- **GIVEN** an in-corpus answer with all v1 guardrails passing
- **WHEN** the user selects the end-user layout
- **THEN** the guardrail log is not shown
- **AND** the conversation still shows the answer

### Requirement: L1 accordion
In the staff layout the interface SHALL include a “Calidad L1” section that starts collapsed and renders the last static L1 results when expanded. It MUST NOT run evals in the browser. If the stored file is the unpublished shipped sample, the expanded section SHALL say the numbers are a sample and not an operator run. Results from an operator run need no such banner. The end-user layout SHALL NOT show Calidad L1.

#### Scenario: Accordion starts collapsed
- **GIVEN** the interface has just loaded
- **WHEN** the user has not expanded Calidad L1
- **THEN** the L1 numbers are not shown in the main chat column

#### Scenario: Accordion is static
- **GIVEN** the staff layout
- **AND** a stored L1 results file
- **WHEN** the user expands Calidad L1
- **THEN** citation-id exact, hit@5, and A vs B from that file are shown
- **AND** no eval request is sent to a model from the client

#### Scenario: Unpublished fixture is labeled
- **GIVEN** the staff layout
- **AND** only the shipped unpublished L1 results exist
- **WHEN** the user expands Calidad L1
- **THEN** the section states that the numbers are a sample or unpublished

#### Scenario: End-user layout hides Calidad L1
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at the screen
- **THEN** Calidad L1 is not shown
