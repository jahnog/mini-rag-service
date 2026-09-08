## MODIFIED Requirements

### Requirement: Automated tests with fakes
The project SHALL provide a test command that runs unit and acceptance tests with fakes (no live LLM key required for L1) and SHALL emit a coverage report for the deterministic core. That default command MUST NOT require a running serving process, live mail, a browser, or a language-model key. Live acceptance against the local serving process SHALL be a separate operator command and MUST NOT run as part of the default command. The live BCRA catalog download command MUST NOT execute live acceptance.

#### Scenario: Default test command
- **GIVEN** the repository test command
- **WHEN** it runs
- **THEN** unit and Gherkin suites execute with fakes
- **AND** a coverage report file is produced
- **AND** live mail, a browser, and a running serving process are not required

#### Scenario: Live acceptance is not the default
- **GIVEN** the repository default test command
- **WHEN** it runs
- **THEN** live acceptance scenarios against the local serving process do not execute

#### Scenario: Catalog download does not run live acceptance
- **GIVEN** the live BCRA catalog download command
- **WHEN** it runs
- **THEN** live acceptance scenarios against the local serving process do not execute
