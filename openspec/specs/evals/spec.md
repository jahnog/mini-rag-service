# evals Specification

## Purpose

Run retrieval and generation evaluation as a separate operator vertical from chat serving and ingest, so scoring never loads in the API process.

## Requirements

### Requirement: Eval vertical is not chat
Evaluation SHALL be an operator module distinct from chat serving and corpus ingest. Starting the chat process MUST NOT load evaluation scoring. The operator evaluation command MAY use chat retrieval and generate-from-context. Chat answering MUST NOT depend on evaluation scoring.

#### Scenario: Chat starts without eval scoring
- **GIVEN** the evaluation command is not running
- **WHEN** the chat process starts and the user asks an in-corpus question
- **THEN** a structured chat response is still returned

#### Scenario: Operator eval does not boot the assistant UI
- **GIVEN** the operator evaluation command
- **WHEN** it runs
- **THEN** it does not start the assistant interface
- **AND** it still writes the static L1 results document

#### Scenario: Default tests do not run L1
- **GIVEN** the project test command
- **WHEN** it runs in CI
- **THEN** it does not run a paid L1 evaluation
- **AND** chat tests still pass without it

### Requirement: Operator-only composition
The evaluation command SHALL compose its own retrieval suite and generation suite. Refresh MUST NOT run evaluation unless the operator opts in. There SHALL NOT be an HTTP evaluation endpoint.

#### Scenario: Weekday refresh skips eval
- **GIVEN** a scheduled refresh
- **WHEN** it completes without an opt-in flag
- **THEN** evaluation is not executed

#### Scenario: No eval HTTP surface
- **GIVEN** the chat process is running
- **WHEN** a client inspects the HTTP API
- **THEN** there is no evaluation run endpoint
