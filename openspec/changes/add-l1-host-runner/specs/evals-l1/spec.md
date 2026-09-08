## ADDED Requirements

### Requirement: Dump-host published run
An operator L1 run on the host that stores the dump SHALL score against that dump’s index when the index is ready. Published staff L1 numbers (Calidad L1 without the unpublished/sample banner) MUST come from an operator run on that dump whose index was ready. A run on a machine whose index is not ready MUST still be labeled unpublished or sample and MUST NOT be presented as dump quality. A shipped unpublished sample MAY still be shown until a published run exists. Citation-id exact SHALL remain the headline metric.

#### Scenario: Dump-host run is published
- **GIVEN** the dump index is ready on the host
- **WHEN** an operator L1 run completes on that host
- **THEN** the static results document is not labeled unpublished or sample
- **AND** citation-id exact is presented as the headline number

#### Scenario: Run without a ready index stays sample
- **GIVEN** no dump has been ingested on the machine that runs L1
- **WHEN** an operator L1 run completes
- **THEN** the results are labeled unpublished or sample
- **AND** they are not presented as dump quality

#### Scenario: Invented Com. still scores silencio on the dump host
- **GIVEN** a gold row for Comunicación A 9999
- **AND** the dump index is ready
- **WHEN** L1 is scored on the dump host
- **THEN** gold finding is silencio
- **AND** gold citations are empty

### Requirement: Host install preserves operator L1
Installing or updating application code on the dump host MUST NOT replace an operator L1 results document with the shipped unpublished sample. When no results document exists on that host, the install MAY seed the shipped unpublished sample and MUST NOT seed a published run from another machine.

#### Scenario: Second install keeps operator numbers
- **GIVEN** an operator L1 run has replaced the sample on the dump host
- **WHEN** the operator updates application code on that host
- **THEN** the stored operator results remain
- **AND** they are not the shipped unpublished sample

#### Scenario: First install may seed sample
- **GIVEN** the dump host has no L1 results document
- **AND** the operator machine has the shipped unpublished sample
- **WHEN** the operator installs the application
- **THEN** a shipped unpublished sample MAY be present
- **AND** it is labeled unpublished or sample

#### Scenario: First install does not seed a published laptop run
- **GIVEN** the dump host has no L1 results document
- **AND** the operator machine has a published L1 results document
- **WHEN** the operator installs the application
- **THEN** that published document is not installed as the host results
- **AND** the host results are missing or the shipped unpublished sample

## MODIFIED Requirements

### Requirement: Static results file
L1 SHALL write a static results document that the assistant UI reads. The browser MUST NOT compute L1 scores. Refresh MUST NOT run L1 unless the operator opts in. A shipped placeholder results document MAY exist so the UI is not empty. The UI MUST label those numbers as unpublished or sample until a published operator L1 run has replaced them. The placeholder MUST mark judged metrics skipped, not zero.

#### Scenario: UI reads last run
- **GIVEN** a results file from the last L1 run
- **WHEN** the user opens Calidad L1
- **THEN** those stored numbers are shown
- **AND** no eval model is invoked in the client

#### Scenario: Shipped placeholder is labeled
- **GIVEN** only the shipped unpublished results document exists
- **WHEN** the user expands Calidad L1
- **THEN** the numbers are shown as a sample or unpublished
- **AND** they are not presented as an operator run
- **AND** judged metrics are not shown as 0

#### Scenario: Weekday refresh skips L1
- **GIVEN** a scheduled refresh
- **WHEN** it completes without an opt-in flag
- **THEN** L1 is not executed
