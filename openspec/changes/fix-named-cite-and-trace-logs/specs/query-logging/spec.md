## ADDED Requirements

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
