# assistant-ui Specification

## Purpose

Give staff one screen with cited clauses, a this-query trust panel, and last-run L1, and give end users a reduced chat layout on that same screen — without a second product UI.

## Requirements

### Requirement: Banner
The assistant interface SHALL show that the corpus is a BCRA CAMEX unofficial extract, `to_as_of`, `last_refresh`, last Comunicación id, and document count.

#### Scenario: Banner after ingest
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the interface loads
- **THEN** those values are visible without opening a settings page

### Requirement: Observatory shell
The assistant interface SHALL be one screen with a topbar, a dominant chat stage, a side inspector, and a footer. The topbar SHALL show that the corpus is a BCRA CAMEX unofficial extract and SHALL show `to_as_of`, `last_refresh`, last Comunicación id, and document count as chips without opening a settings page. The chat stage SHALL hold the conversation, the question input, suggested prompts, send, Clear, and the abstain banner when it applies. The side inspector SHALL hold citation cards, the this-query trust log, and the Calidad L1 section. The footer SHALL state that the extract is unofficial, not BCRA, not legal advice, and dated as of `last_refresh`. On a wide viewport the chat stage SHALL sit to the left of the inspector. On a narrow viewport the inspector SHALL sit below the chat stage.

#### Scenario: Freeze chips on load
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464, and a document count
- **WHEN** the interface loads
- **THEN** the topbar shows those values as chips
- **AND** the unofficial CAMEX extract wording is visible
- **AND** no settings page is required

#### Scenario: Wide layout keeps chat dominant
- **GIVEN** the interface is shown on a wide viewport
- **WHEN** the user looks at the screen
- **THEN** the chat stage is on the left
- **AND** the inspector is on the right

#### Scenario: Narrow layout stacks the inspector
- **GIVEN** the interface is shown on a narrow viewport
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

### Requirement: Dark observatory chrome
The assistant interface SHALL use a dark background, glass panels, kicker labels, and pill badges on that one screen. Suggested prompts SHALL appear as pills whose text is the existing canned mix (tipo de cambio de referencia A 3500/A 8359, liquidación de exportaciones, a 2001–2002 superseded-trap, and Com. A 9999). Chat, prompts, citations, and trust MUST remain usable without opening a second page.

#### Scenario: Suggested prompts remain pills on the stage
- **GIVEN** the interface is shown
- **WHEN** the user looks at suggested prompts
- **THEN** they appear as pills on the chat stage
- **AND** three prompts are answerable from the dump
- **AND** one asks for a comunicación that is not in the dump
- **AND** none is a generic “explain the BCRA”

#### Scenario: One screen remains usable
- **GIVEN** the interface is shown
- **WHEN** the user asks a named Com. A that is in the dump
- **THEN** the answer, citation cards, and trust log are on the same screen
- **AND** the interface does not open a second product UI

### Requirement: Chat and canned prompts
The interface SHALL provide a chat input, three suggested prompts that are answerable from the dump (tipo de cambio de referencia A 3500/A 8359, liquidación de exportaciones, and a 2001–2002 superseded-trap), and one out-of-corpus prompt (Com. A 9999).

#### Scenario: Suggested prompts mix answerable and silencio
- **GIVEN** the interface is shown
- **WHEN** the user looks at suggested prompts
- **THEN** three prompts are answerable from the dump
- **AND** one asks for a comunicación that is not in the dump
- **AND** none is a generic “explain the BCRA”

### Requirement: Citation inspector
The interface SHALL show citation cards as the visible inspector, with Comunicación id, fecha, punto when known, a short snippet, a copy-id action, and the official bcra.gob.ar PDF URL. A raw structured dump MUST NOT be the primary inspector surface. Clicking a card SHALL update the inspector, not navigate away. Copy-id SHALL place the dump document id on the clipboard (for example A8359), matching the citation id.

#### Scenario: Citation card
- **GIVEN** an answer that cites A 8359
- **WHEN** the user inspects citations
- **THEN** they see A 8359, its date, a snippet, and a bcra.gob.ar link
- **AND** the visible inspector is the citation cards, not a raw structured dump

#### Scenario: Copy id
- **GIVEN** a citation card for A 8359
- **WHEN** the user uses copy-id
- **THEN** the dump id A8359 is placed on the clipboard

#### Scenario: Click stays in inspector
- **GIVEN** an answer that cites A 8359
- **WHEN** the user clicks that citation card
- **THEN** the inspector updates to A 8359
- **AND** the interface does not navigate away from the assistant

### Requirement: Trust panel and abstain banner
The interface SHALL show the per-query guardrail log as pass, warn, or block chips and SHALL show an abstain banner in the chat stage when finding is silencio.

#### Scenario: Silencio banner
- **GIVEN** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible in the chat stage
- **AND** the named guardrail appears in the panel as a chip

#### Scenario: In-corpus trust panel
- **GIVEN** an in-corpus answer with all v1 guardrails passing
- **WHEN** the answer is rendered
- **THEN** the trust panel shows those rules as pass chips

### Requirement: L1 accordion
The interface SHALL include a “Calidad L1” section that starts collapsed and renders the last static L1 results when expanded. It MUST NOT run evals in the browser. If the stored file is the unpublished shipped sample, the expanded section SHALL say the numbers are a sample and not an operator run. Results from an operator run need no such banner.

#### Scenario: Accordion starts collapsed
- **GIVEN** the interface has just loaded
- **WHEN** the user has not expanded Calidad L1
- **THEN** the L1 numbers are not shown in the main chat column

#### Scenario: Accordion is static
- **GIVEN** a stored L1 results file
- **WHEN** the user expands Calidad L1
- **THEN** citation-id exact, hit@5, and A vs B from that file are shown
- **AND** no eval request is sent to a model from the client

#### Scenario: Unpublished fixture is labeled
- **GIVEN** only the shipped unpublished L1 results exist
- **WHEN** the user expands Calidad L1
- **THEN** the section states that the numbers are a sample or unpublished

### Requirement: Clear
The interface SHALL provide a Clear control and SHALL treat typed `/clear` as the same action. Session id SHALL persist across turns in the same UI session until cleared.

#### Scenario: Clear button
- **GIVEN** a session with prior turns
- **WHEN** the user clicks Clear
- **THEN** the next question does not use those turns

#### Scenario: Session id persists
- **GIVEN** the interface has minted a session id
- **WHEN** the user sends a second question without clearing
- **THEN** that question uses the same session id
