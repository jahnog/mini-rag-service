## ADDED Requirements

### Requirement: Reasoning trace
When the language model is called and the provider returns a reasoning trace, the structured response SHALL include that trace as `thinking`, separate from `answer`. `thinking` MUST NOT be concatenated into `answer` or into a `Fuente:` line. `thinking` MUST NOT include the JSON answer object when the provider copies that object into the reasoning trace. When the provider returns no trace, `thinking` SHALL be absent, empty, or null. Paths that do not call the language model (`/clear`, a blocking guardrail, empty retrieval, index not ready) SHALL NOT invent a thinking trace. A failed language-model call SHALL leave `thinking` absent, empty, or null and MUST NOT put exception text in `thinking` or `answer`. Session memory SHALL store the answer text, not the thinking trace.

#### Scenario: In-corpus answer with a trace
- **GIVEN** the index is ready
- **AND** the language-model provider returns a reasoning trace with the cited JSON answer
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the response `thinking` contains that trace
- **AND** `answer` still contains a `Fuente:` line
- **AND** `answer` does not contain the thinking trace concatenated into the clause
- **AND** the response includes `last_refresh` and `to_as_of`

#### Scenario: In-corpus answer without a trace
- **GIVEN** the index is ready
- **AND** the language-model provider returns a cited JSON answer and no reasoning trace
- **WHEN** the user asks an in-corpus vigente question
- **THEN** `thinking` is absent, empty, or null
- **AND** `answer` still contains a `Fuente:` line

#### Scenario: Named Com. A still cites the dump
- **GIVEN** the index is ready
- **AND** Comunicación A 8359 is in the dump
- **AND** the language-model provider returns a reasoning trace
- **WHEN** the user asks what Comunicación A 8359 says
- **THEN** the chat response citations include dump id `A8359`
- **AND** `thinking` is the provider trace, not the citation id

#### Scenario: Empty retrieval is silencio without thinking
- **GIVEN** retrieval returns no usable hits
- **WHEN** the user asks a question
- **THEN** finding is silencio
- **AND** the language model is not called
- **AND** `thinking` is absent, empty, or null

#### Scenario: Typed /clear has no thinking
- **GIVEN** a session with prior turns
- **WHEN** the user sends `/clear`
- **THEN** the acknowledgement has no retrieved citations
- **AND** the language model is not called
- **AND** `thinking` is absent, empty, or null

#### Scenario: Failed language-model call has no thinking
- **GIVEN** the index is ready
- **WHEN** the language-model call fails or no key is configured
- **THEN** finding is `silencio`
- **AND** `abstain_reason` is `llm_unavailable`
- **AND** `thinking` is absent, empty, or null
- **AND** the answer does not contain exception text

#### Scenario: JSON body copied into the reasoning trace is stripped
- **GIVEN** the index is ready
- **AND** the language-model provider returns a reasoning trace that also contains the JSON answer object
- **WHEN** the user asks an in-corpus vigente question
- **THEN** `thinking` does not include that JSON object
- **AND** `answer` still comes from the JSON body

#### Scenario: JSON thinking with an answer property shows that text
- **GIVEN** the index is ready
- **AND** the language-model provider returns a reasoning trace that is a JSON object with an `answer` string
- **WHEN** the user asks an in-corpus vigente question
- **THEN** `thinking` is that `answer` string
- **AND** `thinking` does not include the JSON braces or the `answer` key

#### Scenario: Follow-up does not replay thinking
- **GIVEN** the user asked about punto 3.8.5 and received a cited answer with a thinking trace
- **WHEN** the user asks “y ese punto?” in the same session
- **THEN** the new answer includes a citation that exists in the dump
- **AND** session memory for the prior turn is the answer text, not the thinking trace

## MODIFIED Requirements

### Requirement: Structured cited answer
The system SHALL return a structured response that includes: answer text with a `Fuente:` line when citations exist, finding (`obligacion`, `permiso`, `prohibicion`, `definicion`, `procedimiento`, or `silencio`), citations (id, tipo, fecha, punto when known, snippet, source URL), abstain flag and reason, `last_refresh`, `to_as_of`, per-query guardrail log, retrieval sidecar, request id, session id, and optional `thinking` (a reasoning trace from the language-model provider; absent, empty, or null when none). Citation `id` SHALL be the dump document id (`A8359` or `texto_ordenado`), never an internal chunk id. Citation `tipo` SHALL be `A` for Comunicaciones A (including reprint events) and SHALL NOT be `A` for the texto ordenado. Quoted clauses SHALL remain in Spanish even if the question is English. Abstain SHALL be true if and only if finding is `silencio`. Extra unknown fields MUST be rejected at the boundary. A chat request MUST NOT accept `thinking` as an input field.

#### Scenario: Successful in-corpus answer
- **GIVEN** the index is ready
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the answer contains a `Fuente:` line naming TO or Com. “A” and a punto when applicable
- **AND** each citation id exists in the dump
- **AND** quoted clauses remain in Spanish even if the question is English
- **AND** the response includes `last_refresh` and `to_as_of`

#### Scenario: Empty retrieval is silencio
- **GIVEN** retrieval returns no usable hits
- **WHEN** the user asks a question
- **THEN** finding is silencio
- **AND** abstain is true
- **AND** citations are empty
- **AND** the answer names `last_refresh`

#### Scenario: Chat request does not accept thinking as input
- **GIVEN** a ready index
- **WHEN** a client posts a chat body that includes a `thinking` field
- **THEN** the request is rejected
- **AND** extra unknown fields remain rejected at the boundary
