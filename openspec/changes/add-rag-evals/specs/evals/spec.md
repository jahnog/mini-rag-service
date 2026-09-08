## Purpose

Run retrieval and generation evaluation as a separate operator vertical from chat serving and ingest, so scoring and the judge never load in the API process.

## ADDED Requirements

### Requirement: Eval vertical is not chat
Evaluation SHALL be an operator module distinct from chat serving and corpus ingest. Starting the chat process MUST NOT load evaluation scoring or the judge. The operator evaluation command MAY use chat retrieval and generate-from-context. Chat answering MUST NOT depend on evaluation scoring.

#### Scenario: Chat starts without the eval extra
- **GIVEN** the optional judge extra is not installed
- **WHEN** the chat process starts and the user asks an in-corpus question
- **THEN** a structured chat response is still returned

#### Scenario: Operator eval does not boot the assistant UI
- **GIVEN** the operator evaluation command
- **WHEN** it runs
- **THEN** it does not start the assistant interface
- **AND** it still writes the static L1 results document

#### Scenario: Default tests do not import the judge
- **GIVEN** the project test command
- **WHEN** it runs in CI
- **THEN** it does not require the judge extra
- **AND** chat tests still pass without it

### Requirement: Operator-only composition
The evaluation command SHALL compose its own retrieval suite, generation suite, judge, and collector sink. Refresh MUST NOT run evaluation unless the operator opts in. There SHALL NOT be an HTTP evaluation endpoint.

#### Scenario: Weekday refresh skips eval
- **GIVEN** a scheduled refresh
- **WHEN** it completes without an opt-in flag
- **THEN** evaluation is not executed

#### Scenario: No eval HTTP surface
- **GIVEN** the chat process is running
- **WHEN** a client inspects the HTTP API
- **THEN** there is no evaluation run endpoint
