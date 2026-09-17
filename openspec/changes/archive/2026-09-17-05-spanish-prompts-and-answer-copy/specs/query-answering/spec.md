## MODIFIED Requirements

### Requirement: Structured cited answer
The system SHALL return a structured response that includes: answer text with a `Fuente:` line when citations exist, finding (`obligacion`, `permiso`, `prohibicion`, `definicion`, `procedimiento`, or `silencio`), citations (id, tipo, fecha, punto when known, snippet, source URL), abstain flag and reason, `last_refresh`, `to_as_of`, per-query guardrail log, retrieval sidecar, request id, session id, and optional `thinking` (a reasoning trace from the language-model provider; absent, empty, or null when none). Citation `id` SHALL be the dump document id (`A8359` or `texto_ordenado`), never an internal chunk id. Citation `tipo` SHALL be `A` for Comunicaciones A (including reprint events) and SHALL NOT be `A` for the texto ordenado. Quoted clauses SHALL remain in Spanish even if the question is English. The visible answer SHALL name the dump freeze as a Spanish sentence of the form "Según el dump del <fecha> (texto ordenado al <to_as_of>)." where `<fecha>` is the calendar date of `last_refresh`; it MUST NOT print `last_refresh=` or `to_as_of=` identifiers. Abstain SHALL be true if and only if finding is `silencio`. Extra unknown fields MUST be rejected at the boundary. A chat request MUST NOT accept `thinking` as an input field.

#### Scenario: Successful in-corpus answer
- **GIVEN** the index is ready
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the answer contains a `Fuente:` line naming TO or Com. “A” and a punto when applicable
- **AND** each citation id exists in the dump
- **AND** quoted clauses remain in Spanish even if the question is English
- **AND** the response includes `last_refresh` and `to_as_of`
- **AND** the answer ends with the freeze sentence naming the dump date and `to_as_of`

#### Scenario: Empty retrieval is silencio
- **GIVEN** retrieval returns no usable hits
- **AND** last_refresh is 2026-09-01T00:00:00+00:00 and to_as_of is A8307
- **WHEN** the user asks a question
- **THEN** finding is silencio
- **AND** abstain is true
- **AND** citations are empty
- **AND** the answer contains "Según el dump del 2026-09-01 (texto ordenado al A8307)."
- **AND** the answer does not contain "last_refresh="

#### Scenario: Chat request does not accept thinking as input
- **GIVEN** a ready index
- **WHEN** a client posts a chat body that includes a `thinking` field
- **THEN** the request is rejected
- **AND** extra unknown fields remain rejected at the boundary

## ADDED Requirements

### Requirement: Spanish instructions with finding definitions
The language-model instructions SHALL be written in Spanish. The system prompt SHALL define each finding label in one sentence (obligacion, prohibicion, permiso, definicion, procedimiento, silencio), SHALL state the citation rules (dump document ids only, verbatim snippet, `Fuente:` line, Spanish quotes), and SHALL include one example JSON object with a citation and one without evidence. The per-turn prompt SHALL keep the retrieved documents inside a random delimiter with a data-only framing and SHALL present each chunk as `[chunk_id=<doc_id> punto=<punto>] <text>`.

#### Scenario: System prompt defines findings
- **GIVEN** the language-model adapter
- **WHEN** a call is made
- **THEN** the system message contains "obligacion (" and "silencio (" definitions
- **AND** it contains a `Fuente:` instruction and both JSON examples

#### Scenario: Per-turn prompt keeps the chunk line format
- **GIVEN** a retrieved chunk of `texto_ordenado` punto 3.8.5
- **WHEN** the per-turn prompt is built
- **THEN** it contains a line starting with `[chunk_id=texto_ordenado punto=3.8.5] `
- **AND** the documents are wrapped by the turn's random delimiter

### Requirement: Blocked answers use human copy
When a guardrail blocks a turn, the visible answer SHALL be a Spanish sentence starting with "No puedo responder" that explains the reason in user terms and MUST NOT print the internal rule id for rules with defined copy (length, secrets, no-advice, injection, scope, no-advice-output, secrets-output, prompt-leak, chunk-injection). The guardrail log keeps the rule id.

#### Scenario: Weather block copy
- **GIVEN** the user asks about the weather in Madrid
- **WHEN** the request is processed
- **THEN** the answer is "No puedo responder: la pregunta no es sobre la normativa cambiaria CAMEX del BCRA." followed by the freeze sentence
- **AND** the guardrail log names `scope` as `block`

#### Scenario: Injection block copy
- **GIVEN** the user submits a jailbreak
- **WHEN** the request is processed
- **THEN** the answer starts with "No puedo responder: la pregunta intenta cambiar mis instrucciones."
