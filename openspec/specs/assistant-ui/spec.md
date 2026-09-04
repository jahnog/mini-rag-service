# assistant-ui Specification

## Purpose

Give a reviewer one screen: chat with cited clauses, a trust panel for this query, and a last-run L1 accordion — without a second product UI.

## Requirements

### Requirement: Banner
The assistant interface SHALL show that the corpus is a BCRA CAMEX unofficial extract, `to_as_of`, `last_refresh`, last Comunicación id, and document count.

#### Scenario: Banner after ingest
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the interface loads
- **THEN** those values are visible without opening a settings page

### Requirement: Chat and canned prompts
The interface SHALL provide a chat input, three suggested prompts that are answerable from the dump (tipo de cambio de referencia A 3500/A 8359, liquidación de exportaciones, and a 2001–2002 superseded-trap), and one out-of-corpus prompt (Com. A 9999).

#### Scenario: Suggested prompts mix answerable and silencio
- **GIVEN** the interface is shown
- **WHEN** the user looks at suggested prompts
- **THEN** three prompts are answerable from the dump
- **AND** one asks for a comunicación that is not in the dump
- **AND** none is a generic “explain the BCRA”

### Requirement: Citation inspector
The interface SHALL show citation cards with Comunicación id, fecha, punto when known, a short snippet, a copy-id action, and the official bcra.gob.ar PDF URL. Clicking a card SHALL update the inspector, not navigate away. Copy-id SHALL place the dump document id on the clipboard (for example A8359), matching the citation id.

#### Scenario: Citation card
- **GIVEN** an answer that cites A 8359
- **WHEN** the user inspects citations
- **THEN** they see A 8359, its date, a snippet, and a bcra.gob.ar link

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
The interface SHALL show the per-query guardrail log and SHALL show an abstain banner when finding is silencio.

#### Scenario: Silencio banner
- **GIVEN** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible
- **AND** the named guardrail appears in the panel

#### Scenario: In-corpus trust panel
- **GIVEN** an in-corpus answer with all v1 guardrails passing
- **WHEN** the answer is rendered
- **THEN** the trust panel shows those rules as pass

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
