## MODIFIED Requirements

### Requirement: L1 accordion
In the staff layout the interface SHALL include a “Calidad L1” section that starts collapsed and renders the last static L1 results when expanded. It MUST NOT run evals in the browser. The expanded section SHALL show two headings, retrieval and generation, when those blocks exist. A skipped suite SHALL be labeled skipped and MUST NOT be shown as a score of 0. If the stored file is the unpublished shipped sample, the expanded section SHALL say the numbers are a sample and not an operator run. Results from an operator run need no such banner. The end-user layout SHALL NOT show Calidad L1.

#### Scenario: Accordion starts collapsed
- **GIVEN** the interface has just loaded
- **WHEN** the user has not expanded Calidad L1
- **THEN** the L1 numbers are not shown in the main chat column

#### Scenario: Accordion is static
- **GIVEN** the staff layout
- **AND** a stored L1 results file
- **WHEN** the user expands Calidad L1
- **THEN** citation-id exact, hit@5, and A vs B from that file are shown
- **AND** retrieval and generation headings are shown when those blocks exist
- **AND** no eval request is sent to a model from the client

#### Scenario: Unpublished fixture is labeled
- **GIVEN** the staff layout
- **AND** only the shipped unpublished L1 results exist
- **WHEN** the user expands Calidad L1
- **THEN** the section states that the numbers are a sample or unpublished

#### Scenario: Skipped generation is not zero
- **GIVEN** the staff layout
- **AND** the stored L1 results mark generation skipped
- **WHEN** the user expands Calidad L1
- **THEN** generation is labeled skipped
- **AND** faithfulness is not shown as 0

#### Scenario: End-user layout hides Calidad L1
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at the screen
- **THEN** Calidad L1 is not shown
