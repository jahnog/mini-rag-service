## ADDED Requirements

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
