## ADDED Requirements

### Requirement: Published L1 document is served
The production-smoke command SHALL request `GET /l1` from the running public process and SHALL fail (not skip) when the response is not HTTP 200, when it lacks `retrieval`, `generation`, `judge`, or `n`, or when `unpublished` or `sample` is true. It MUST NOT run L1.

#### Scenario: Host serves a published run
- **GIVEN** the operator invoked the production-smoke command
- **WHEN** the client requests `GET /l1`
- **THEN** the response is HTTP 200
- **AND** `unpublished` and `sample` are false
- **AND** `retrieval`, `generation`, `judge`, and `n` are present

#### Scenario: Host has only the stub
- **GIVEN** the public process has no results document
- **WHEN** the production-smoke command requests `GET /l1`
- **THEN** the command fails and names the missing published run
