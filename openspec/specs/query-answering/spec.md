# query-answering Specification

## Purpose

Turn a user question into a short cited answer or silencio, with a structured response, small session memory, and a clear command.

## Requirements

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

### Requirement: Messy model citations must not drop dump hits
When the index is ready and retrieval returned dump hits, the system SHALL still return those dump document ids as chat citations even if the language-model JSON has `citations` as a string, as a list of strings, or as objects that omit `tipo`. Citation `id` SHALL be a dump document id (`texto_ordenado` or `A####`), never an internal chunk id. Citation `tipo` SHALL be `TO` for the texto ordenado and `A` for Comunicaciones A. `POST /chat` citations SHALL be objects with `id` and `tipo`, not a string. `abstain_reason` MUST NOT be `llm_unavailable` solely because `citations` was messy. If the model omits usable citation ids, the system SHALL still cite from the dump hits. Quoted clauses SHALL remain in Spanish even if the question is English. The answer SHALL name `last_refresh` and `to_as_of` on a successful in-corpus turn.

#### Scenario: Citations field is a Fuente string
- **GIVEN** the index is ready
- **AND** retrieval returned dump hits including the texto ordenado
- **WHEN** the user asks a vigente CAMEX question
- **AND** the language model returns JSON whose `citations` value is the string `Fuente: texto_ordenado`
- **THEN** the chat response citations include dump id `texto_ordenado`
- **AND** that citation’s `tipo` is `TO`
- **AND** citations in `POST /chat` are objects, not a string
- **AND** `abstain_reason` is not `llm_unavailable`
- **AND** the answer names `last_refresh` and `to_as_of`

#### Scenario: Citations field is a list of dump ids
- **GIVEN** the index is ready
- **AND** retrieval returned dump hits
- **WHEN** the language model returns JSON whose `citations` value is a list of dump ids such as `A8359`
- **THEN** the chat response citations include dump id `A8359`
- **AND** that citation’s `tipo` is `A`

#### Scenario: Citation object omits tipo
- **GIVEN** the index is ready
- **AND** retrieval returned dump hits for the texto ordenado
- **WHEN** the language model returns a citation object with dump id `texto_ordenado` and no `tipo`
- **THEN** the chat response citation for that id has `tipo` `TO`

#### Scenario: Model omits usable citation ids
- **GIVEN** the index is ready
- **AND** retrieval returned dump hits
- **WHEN** the language model returns JSON with an answer and no usable citation ids
- **THEN** the chat response citations still use dump document ids from those hits
- **AND** `abstain_reason` is not `llm_unavailable`

#### Scenario: Named Com. A still cites the dump
- **GIVEN** the index is ready
- **AND** Comunicación A 8359 is in the dump
- **WHEN** the user asks what Comunicación A 8359 says
- **AND** the language model returns messy `citations`
- **THEN** the chat response citations include dump id `A8359`
- **AND** `tipo` is `A`

#### Scenario: Clear session still does not retrieve
- **GIVEN** a session that already received dump citations
- **WHEN** the user sends `/clear`
- **THEN** the acknowledgement has no retrieved citations
- **AND** the clear path does not call the language model

### Requirement: Language-model call failure is still silencio
When the language-model call fails or no language-model key is configured, the system SHALL return finding `silencio` with `abstain_reason` `llm_unavailable`. The answer MUST NOT contain exception text. Unparseable non-JSON model bodies MAY use the same silencio path. Empty retrieval remains silencio without a language-model call (existing empty-hits contract).

#### Scenario: Missing key or failed call
- **GIVEN** the index is ready
- **WHEN** the language-model call fails or no key is configured
- **THEN** finding is `silencio`
- **AND** `abstain_reason` is `llm_unavailable`
- **AND** the answer does not contain exception text
- **AND** the answer names `last_refresh`

#### Scenario: Empty retrieval still does not call the model
- **GIVEN** retrieval returns no usable hits
- **WHEN** the user asks a question
- **THEN** finding is `silencio`
- **AND** citations are empty
- **AND** the language model is not called
