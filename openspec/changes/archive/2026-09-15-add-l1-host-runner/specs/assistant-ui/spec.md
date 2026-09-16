## MODIFIED Requirements

### Requirement: L1 accordion
In the staff layout the interface SHALL include a “Calidad L1” section that starts collapsed and renders the last static L1 results when expanded. It MUST NOT run evals in the browser. The expanded section SHALL show two headings, retrieval and generation, when those blocks exist. A skipped suite SHALL be labeled skipped and MUST NOT be shown as a score of 0. If the stored file is labeled unpublished or sample, the expanded section SHALL say the numbers are a sample and not an operator run. That banner SHALL remain whenever the stored file is labeled unpublished or sample. After the serving process reloads, the expanded section SHALL show the stored document as-is. The end-user layout SHALL NOT show Calidad L1.

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

#### Scenario: Published dump-host run has no sample banner
- **GIVEN** the staff layout
- **AND** the dump index was ready
- **AND** the stored L1 results are not labeled unpublished or sample
- **AND** the serving process has reloaded after a dump-host operator L1 run
- **WHEN** the user expands Calidad L1
- **THEN** the stored operator numbers are shown
- **AND** the section does not state that the numbers are a sample or unpublished
- **AND** retrieval and generation headings are shown when those blocks exist

#### Scenario: Sample banner survives reload when unpublished
- **GIVEN** the staff layout
- **AND** the stored L1 results are labeled unpublished or sample
- **AND** the serving process has reloaded
- **WHEN** the user expands Calidad L1
- **THEN** the section states that the numbers are a sample or unpublished

#### Scenario: End-user layout hides Calidad L1
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at the screen
- **THEN** Calidad L1 is not shown
