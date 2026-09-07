## Purpose

Give operators a durable dump-host record of each completed chat turn (the user question, the cited answer or silencio, and the v1 guardrail log) and of each L1 run’s published metrics, without running evals in the browser or changing the chat contract.

## ADDED Requirements

### Requirement: Chat turn on console and file
Every completed chat turn SHALL be written to the process console and to a log file on the dump host. The record SHALL include the user message, the answer text, finding, citation dump ids, abstain flag, request id, session id, and the full v1 guardrail log (each rule with verdict `pass`, `warn`, or `block` and a short detail). The file SHALL remain readable after the process exits. The system MUST NOT require a separate operator command to produce these logs. HTTP and the assistant interface SHALL share this record for the same turn.

#### Scenario: In-corpus turn is logged
- **GIVEN** a ready index
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the console and the log file include that question
- **AND** they include the answer text and finding
- **AND** they include at least one citation dump id
- **AND** they include the v1 guardrail log with each listed rule as pass, warn, or block

#### Scenario: Named Com. A is logged
- **GIVEN** a ready index that holds Comunicación A 3500
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the log record includes citation dump id `A3500`

#### Scenario: File keeps the turn after the process exits
- **GIVEN** a completed chat turn has been logged
- **WHEN** an operator reads the dump-host log file after the process has exited
- **THEN** that file still contains the user message, the answer, and the guardrail log from that turn

### Requirement: Blocked and silencio turns still log
A scope, injection, or no-advice block SHALL still write the turn, including the blocking rule in the guardrail log. `/clear` SHALL still write the turn. A silencio answer SHALL still write the turn with finding `silencio`. Blocked turns SHALL NOT retrieve and SHALL NOT call the language model.

#### Scenario: No-advice block is logged
- **GIVEN** the user asks “Debería comprar dólares?”
- **WHEN** the request is processed
- **THEN** the console and the log file include that question
- **AND** the no-advice rule is `block` in the logged guardrail log
- **AND** finding is silencio
- **AND** the language model is not called

#### Scenario: Typed /clear is logged
- **GIVEN** a session with prior turns
- **WHEN** the user sends `/clear`
- **THEN** the console and the log file include that `/clear` turn
- **AND** the logged citations are empty
- **AND** the language model is not called

#### Scenario: Silencio empty retrieval is logged
- **GIVEN** retrieval returns no usable hits
- **WHEN** the user asks a question
- **THEN** the log record has finding silencio
- **AND** logged citations are empty

### Requirement: L1 run on console and file
After an L1 run writes the static results document the assistant interface already reads, the system SHALL also append the published metrics to the process console and to a log file on the dump host: headline citation-id exact, hit@5, MRR, the slice table, chunking A versus B, unpublished or sample, and the gold-row count. The file SHALL remain readable after a later L1 run overwrites the static results document. Automated tests MUST NOT call a paid language model for this log. The browser MUST NOT compute L1 scores.

#### Scenario: Published metrics are logged after L1
- **GIVEN** an L1 run has completed
- **WHEN** an operator reads the dump-host log file
- **THEN** that file includes citation-id exact as the headline metric
- **AND** it includes hit@5, MRR, and the slice table
- **AND** it includes whether the run is unpublished or sample

#### Scenario: Later L1 overwrite keeps prior log lines
- **GIVEN** an L1 run has already been logged
- **WHEN** a later L1 run overwrites the static results document
- **THEN** the earlier run’s metrics remain in the log file
