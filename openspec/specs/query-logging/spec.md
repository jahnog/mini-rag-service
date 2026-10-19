# query-logging Specification

## Purpose

Give operators a console record of each completed chat turn (the user question, the cited answer or silencio, and the v1 guardrail log) and a durable file of each L1 run’s published metrics, without running evals in the browser or changing the chat contract.

## Requirements

### Requirement: Chat turn on the console
Every completed chat turn SHALL be written to the process console. The record SHALL include the user message, the answer text, finding, citation dump ids, abstain flag, request id, session id, and the full v1 guardrail log (each rule with verdict `pass`, `warn`, or `block` and a short detail). The system MUST NOT require a separate operator command to produce these logs. HTTP and the assistant interface SHALL share this record for the same turn.

#### Scenario: In-corpus turn is logged
- **GIVEN** a ready index
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the console includes that question
- **AND** they include the answer text and finding
- **AND** they include at least one citation dump id
- **AND** they include the v1 guardrail log with each listed rule as pass, warn, or block

#### Scenario: Named Com. A is logged
- **GIVEN** a ready index that holds Comunicación A 3500
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the log record includes citation dump id `A3500`

### Requirement: Thinking trace is not persisted
Each completed chat turn record MUST NOT include the language-model thinking trace. It MUST NOT include the language-model prompt. The record SHALL still include the user message, the answer text, finding, citation dump ids when present, and the guardrail log.

#### Scenario: In-corpus turn with a trace still logs the answer
- **GIVEN** a ready index
- **AND** the language-model provider returns a reasoning trace with a cited JSON answer
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the console includes that question
- **AND** they include the answer text and finding
- **AND** they include at least one citation dump id
- **AND** they do not include the thinking trace

#### Scenario: Named Com. A is logged without thinking
- **GIVEN** a ready index that holds Comunicación A 3500
- **AND** the language-model provider returns a reasoning trace
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the log record includes citation dump id `A3500`
- **AND** the log record does not include the thinking trace

#### Scenario: Silencio empty retrieval is logged without thinking
- **GIVEN** retrieval returns no usable hits
- **WHEN** the user asks a question
- **THEN** the log record has finding silencio
- **AND** logged citations are empty
- **AND** the log record does not include a thinking trace

#### Scenario: Typed /clear is logged without thinking
- **GIVEN** a session with prior turns
- **WHEN** the user sends `/clear`
- **THEN** the console includes that `/clear` turn
- **AND** the language model is not called
- **AND** the log record does not include a thinking trace

### Requirement: Blocked and silencio turns still log
A scope, injection, or no-advice block SHALL still write the turn, including the blocking rule in the guardrail log. `/clear` SHALL still write the turn. A silencio answer SHALL still write the turn with finding `silencio`. Blocked turns SHALL NOT retrieve and SHALL NOT call the language model.

#### Scenario: No-advice block is logged
- **GIVEN** the user asks “Debería comprar dólares?”
- **WHEN** the request is processed
- **THEN** the console includes that question
- **AND** the no-advice rule is `block` in the logged guardrail log
- **AND** finding is silencio
- **AND** the language model is not called

#### Scenario: Typed /clear is logged
- **GIVEN** a session with prior turns
- **WHEN** the user sends `/clear`
- **THEN** the console includes that `/clear` turn
- **AND** the logged citations are empty
- **AND** the language model is not called

#### Scenario: Silencio empty retrieval is logged
- **GIVEN** retrieval returns no usable hits
- **WHEN** the user asks a question
- **THEN** the log record has finding silencio
- **AND** logged citations are empty

### Requirement: L1 run on console and file
After an L1 run writes the static results document the assistant interface already reads, the system SHALL also append the published metrics to the process console and to a log file on the dump host: headline citation-id exact, hit@5, MRR, the slice table, unpublished or sample, and the gold-row count. The file SHALL remain readable after a later L1 run overwrites the static results document. Automated tests MUST NOT call a paid language model for this log. The browser MUST NOT compute L1 scores.

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

### Requirement: Guardrail decision fields on the chat turn
Each completed chat turn record SHALL include, for every guardrail log row, its stage and latency. It SHALL include dump ids that survived retrieval scanning and dump ids dropped by a document rule. It MUST NOT echo secret-shaped tokens in `message`, `answer`, or details. It MUST NOT include the language-model prompt.

#### Scenario: Blocked injection is reconstructable
- **GIVEN** the user submits a jailbreak
- **WHEN** the turn is logged
- **THEN** the record includes injection as `block`
- **AND** `llm_called` is false
- **AND** retrieve is `skipped`

#### Scenario: Secret in the question is not stored
- **GIVEN** the user question contains an `sk-`, `lm-`, or `xai-` shaped token
- **WHEN** the turn is logged
- **THEN** the stored `message` does not contain that token
- **AND** guardrail details do not contain that token

### Requirement: Named-fetch and cite-or-abstain fields on the chat turn
Each completed chat turn record SHALL include the retrieval route (`named`, `vigente`, or `similar` when retrieval ran). When the route is named, it SHALL include the named dump id and the fetched-section character count. When the language model was called, it SHALL include the draft finding and the draft citation dump ids, and per attempted model citation a failure reason (`unknown_id`, `empty_snippet`, or `quote_not_in_hit`) taken from the model snippet **before** any empty-snippet fill, plus a salvage outcome (`replaced_snippet`, `attached_named`, or `none`). A scope, injection, or no-advice block SHALL omit those cite-failure fields. The record MUST NOT include the thinking trace, the language-model prompt, retrieved clause bodies, or secret-shaped tokens.

#### Scenario: Named paraphrased snippet is reconstructable
- **GIVEN** a ready index that holds Comunicación A 3500
- **AND** the language-model draft cites `A3500` with a paraphrased snippet
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the log record includes retrieval route `named`
- **AND** it includes named dump id `A3500`
- **AND** it includes a cite failure `quote_not_in_hit`
- **AND** it includes salvage `replaced_snippet`
- **AND** it does not include the thinking trace

#### Scenario: Weather block has no cite-failure fields
- **GIVEN** a ready index
- **WHEN** the user asks about the weather
- **THEN** the log record includes finding silencio
- **AND** it does not include cite-failure fields
- **AND** the language model is not called

#### Scenario: /clear has no cite-failure fields
- **GIVEN** a session with prior turns
- **WHEN** the user sends `/clear`
- **THEN** the log record includes that `/clear` turn
- **AND** it does not include cite-failure fields
