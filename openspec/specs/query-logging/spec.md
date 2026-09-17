# query-logging Specification

## Purpose

Give operators a durable dump-host record of each completed chat turn (the user question, the cited answer or silencio, and the v1 guardrail log) and of each L1 run’s published metrics, without running evals in the browser or changing the chat contract.

## Requirements

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

### Requirement: Thinking trace is not persisted
Each completed chat turn record MUST NOT include the language-model thinking trace. It MUST NOT include the language-model prompt. The record SHALL still include the user message, the answer text, finding, citation dump ids when present, and the guardrail log.

#### Scenario: In-corpus turn with a trace still logs the answer
- **GIVEN** a ready index
- **AND** the language-model provider returns a reasoning trace with a cited JSON answer
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the console and the log file include that question
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
- **THEN** the console and the log file include that `/clear` turn
- **AND** the language model is not called
- **AND** the log record does not include a thinking trace

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

### Requirement: Guardrail decision fields on the chat turn
Each completed chat turn record SHALL include the policy version, and for every guardrail log row: stage, enforced flag, would-block flag, and latency. It SHALL include dump ids that survived retrieval scanning and dump ids dropped by a document rule. It MUST NOT echo secret-shaped tokens in `message`, `answer`, or details. It MUST NOT include the language-model prompt.

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

### Requirement: Tracer status at process start
When the serving process starts, it SHALL write one log record stating whether per-turn collector export is enabled or disabled. A disabled record SHALL name the reason: collector endpoint unset, tracing extra missing, or register failed. An enabled record SHALL name the collector host and project. The record MUST NOT include a collector API key.

#### Scenario: Missing tracing extra is logged
- **GIVEN** a collector endpoint is configured
- **AND** the tracing extra is not installed
- **WHEN** the serving process starts
- **THEN** the console and the log file include a disabled tracer record
- **AND** the reason is that the tracing extra is missing

#### Scenario: Enabled tracer names host and project
- **GIVEN** a collector endpoint is configured
- **AND** tracing export registers
- **WHEN** the serving process starts
- **THEN** the log record says the tracer is enabled
- **AND** it includes the collector host and project
- **AND** it does not include a collector API key

### Requirement: Compact local traces file
The serving process SHALL append one compact record per tracing span (`chat.turn`, retrieve, and input-block rules such as scope) to a dump-host traces file, whether or not a collector endpoint is configured. Each record SHALL include the span name, a timestamp, and truncated redacted `input.value` when present. It MUST NOT include retrieved clause bodies, the language-model prompt, the thinking trace, or a collector API key. A failure to write that file MUST NOT fail chat.

#### Scenario: Named turn writes local retrieve and chat.turn
- **GIVEN** a ready index that holds Comunicación A 3500
- **AND** no collector endpoint is configured
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the traces file includes a `chat.turn` record
- **AND** it includes a retrieve record
- **AND** a structured chat response is still returned

#### Scenario: Weather writes local scope without retrieve
- **GIVEN** a ready index
- **WHEN** the user asks about the weather
- **THEN** the traces file includes a `chat.turn` record
- **AND** it includes a scope record
- **AND** it does not include a retrieve record for that turn

#### Scenario: Unwritable traces file still answers
- **GIVEN** the traces file cannot be written
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned

### Requirement: Timing and reasoning fields on the chat turn
Every chat turn record SHALL include `retrieve_ms` (wall time of routing and retrieval), `llm_ms` (wall time of the language-model call including any retry), `ttft_ms` (time from the request to the first streamed token, 0 when the model was not called), `thinking_chars` (length of the reasoning trace, 0 when absent) and `abstain_reason` (null when the finding is not silencio). Times SHALL be milliseconds rounded to one decimal.

#### Scenario: In-corpus turn logs timings
- **GIVEN** a ready index and a language model that answers
- **WHEN** the user asks an in-corpus question
- **THEN** the chat turn record has `retrieve_ms` and `llm_ms` greater than or equal to 0
- **AND** `abstain_reason` is null

#### Scenario: Blocked turn logs zero model time
- **GIVEN** an out-of-scope question
- **WHEN** the turn is logged
- **THEN** `llm_ms` and `ttft_ms` are 0
- **AND** `abstain_reason` names the blocking rule
