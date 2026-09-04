## Purpose

Turn a user question into a short cited answer or silencio, with a structured response, small session memory, and a clear command.

## ADDED Requirements

### Requirement: Structured cited answer
The system SHALL return a structured response that includes: answer text with a `Fuente:` line when citations exist, finding (`obligacion`, `permiso`, `prohibicion`, `definicion`, `procedimiento`, or `silencio`), citations (id, tipo, fecha, punto when known, snippet, source URL), abstain flag and reason, `last_refresh`, `to_as_of`, per-query guardrail log, retrieval sidecar, request id, and session id. Citation `id` SHALL be the dump document id (`A8359` or `texto_ordenado`), never an internal chunk id. Citation `tipo` SHALL be `A` for Comunicaciones A (including reprint events) and SHALL NOT be `A` for the texto ordenado. Quoted clauses SHALL remain in Spanish even if the question is English. Abstain SHALL be true if and only if finding is `silencio`. Extra unknown fields MUST be rejected at the boundary.

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

### Requirement: Finding matches the clause
The system SHALL set finding to `obligacion` or `prohibicion` only when the cited snippet actually carries a duty or prohibition (deber, deberá, no podrán, queda prohibido, or a numbered duty). Otherwise it SHALL use definicion, procedimiento, permiso, or silencio. That check SHALL run deterministically after generation and MUST NOT require a second language-model call.

#### Scenario: Advice language is not an obligation
- **GIVEN** a snippet that does not contain a duty verb
- **WHEN** the model would wrap the answer as “conviene registrar…”
- **THEN** finding is not `obligacion`
- **AND** the answer does not add investment or “práctica de mercado” advice
- **AND** no second language-model call is made to fix the finding

### Requirement: HTTP chat contract
The system SHALL expose `POST /chat` that accepts message, optional session id, optional k, and optional filters (tipo, comm_id, date range), and SHALL return the structured response including session id. `POST /chat/stream` MAY exist; if it is not implemented, `POST /chat` remains the contract. Requested `k` MUST NOT exceed the platform maximum.

#### Scenario: Chat request
- **GIVEN** a ready index
- **WHEN** a client posts `{ "message": "Que es el MULC?" }`
- **THEN** the response includes answer, finding, citations, guardrails, session_id, last_refresh, and to_as_of

### Requirement: Requested filters constrain citations
If the client sends tipo, comm_id, or date filters, the system SHALL drop citations that miss those filters before the response is returned. If no citation remains, finding SHALL be silencio. Filter tipo `A` SHALL keep Comunicación A citations (including reprint events) and SHALL drop texto ordenado citations.

#### Scenario: Tipo filter drops mismatches
- **GIVEN** a question that would cite both a TO clause and a Comunicación A
- **WHEN** the client requests filters that allow only tipo A
- **THEN** remaining citations are tipo A
- **AND** none are texto ordenado
- **AND** if none remain, finding is silencio

### Requirement: Session memory
The system SHALL keep the last six messages (three exchanges) per session id. If the client omits session id, the system SHALL mint one. Follow-up questions SHALL still retrieve from the dump; memory MUST NOT invent a circular. Idle sessions SHOULD expire after one hour.

#### Scenario: Follow-up still cites the dump
- **GIVEN** the user asked about punto 3.8.5 and received a cited answer
- **WHEN** the user asks “y ese punto?” in the same session
- **THEN** the new answer includes a citation that exists in the dump

### Requirement: Clear session
The system SHALL clear a session when the user sends `/clear`, uses the UI clear action, or the client posts `POST /chat/clear` with that session id. After clear, the system SHALL NOT use prior turns. The clear acknowledgement SHALL NOT retrieve.

#### Scenario: Typed /clear
- **GIVEN** a session with prior turns
- **WHEN** the user sends `/clear`
- **THEN** subsequent questions do not use those turns
- **AND** the clear response does not include retrieved citations

#### Scenario: HTTP clear
- **GIVEN** a session with prior turns
- **WHEN** a client posts `POST /chat/clear` with that session id
- **THEN** subsequent questions do not use those turns
- **AND** the acknowledgement has no retrieved citations

### Requirement: Index not ready
When the document index is not ready, `POST /chat` SHALL return silencio with abstain reason `index_not_ready` and SHALL NOT invent CAMEX text. That path SHALL NOT retrieve and SHALL NOT call the language model.

#### Scenario: Empty dump
- **GIVEN** no documents have been ingested
- **WHEN** the user asks any CAMEX question
- **THEN** finding is silencio
- **AND** abstain is true
- **AND** abstain_reason is `index_not_ready`
