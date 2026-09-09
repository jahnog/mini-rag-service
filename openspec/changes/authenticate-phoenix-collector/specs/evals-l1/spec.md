## MODIFIED Requirements

### Requirement: Static results file
L1 SHALL write a static results document that the assistant UI reads. The browser MUST NOT compute L1 scores. Refresh MUST NOT run L1 unless the operator opts in. A shipped placeholder results document MAY exist so the UI is not empty. The UI MUST label those numbers as unpublished or sample until an operator L1 run has replaced them. A collector error, including an authentication failure, MUST NOT fail that static write.

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

#### Scenario: Weekday refresh skips L1
- **GIVEN** a scheduled refresh
- **WHEN** it completes without an opt-in flag
- **THEN** L1 is not executed

#### Scenario: Collector auth failure still writes L1
- **GIVEN** a collector endpoint is configured
- **AND** the collector rejects annotations as unauthenticated
- **WHEN** an operator L1 run finishes scoring
- **THEN** the static results document still contains the scores
