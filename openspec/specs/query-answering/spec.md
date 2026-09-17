# query-answering Specification

## Purpose

Turn a user question into a short cited answer or silencio, with a structured response, small session memory, and a clear command.

## Requirements

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
When the index is ready and retrieval returned dump hits, the system SHALL still return a citation when the language-model JSON names a this-turn dump document id even if `citations` is a string, a list of strings, or objects that omit `tipo`. Citation `id` SHALL be a dump document id (`texto_ordenado` or `A####`), never an internal chunk id. Citation `tipo` SHALL be `TO` for the texto ordenado and `A` for Comunicaciones A. `POST /chat` citations SHALL be objects with `id` and `tipo`, not a string. `abstain_reason` MUST NOT be `llm_unavailable` solely because `citations` was messy. If the model omits usable citation ids, the system SHALL force finding `silencio` and empty citations and MUST NOT show the draft. Quoted clauses SHALL remain in Spanish even if the question is English. The answer SHALL name `last_refresh` and `to_as_of` on a successful in-corpus turn.

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
- **THEN** finding is silencio
- **AND** citations are empty
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
When the language-model call fails, the system SHALL return finding `silencio` with an `abstain_reason` that names the failure class: `llm_timeout` when the configured wall-clock bound elapsed, `llm_bad_json` when the model body could not be read as the answer object after one retry with thinking disabled, and `llm_unavailable` for any other failure or when no language-model key is configured. Before declaring `llm_bad_json` the system SHALL strip a surrounding code fence and SHALL accept the last balanced JSON object in the body. Each reason SHALL have its own Spanish answer sentence; the answer MUST NOT contain exception text and SHALL still name the dump freeze. Empty retrieval remains silencio without a language-model call (existing empty-hits contract).

#### Scenario: Missing key or failed call
- **GIVEN** the index is ready
- **WHEN** the language-model call raises a non-timeout, non-parse error or no key is configured
- **THEN** finding is `silencio`
- **AND** `abstain_reason` is `llm_unavailable`
- **AND** the answer does not contain exception text
- **AND** the answer names `last_refresh`

#### Scenario: Fenced JSON is accepted
- **GIVEN** the model body is "```json\n{\"answer\": \"…\", \"finding\": \"definicion\", \"citations\": []}\n```"
- **WHEN** the body is parsed
- **THEN** the answer object is read and the turn is not silencio for a parse reason

#### Scenario: Prose then JSON is accepted
- **GIVEN** the model body is "Aquí va la respuesta: {\"answer\": \"…\", \"finding\": \"silencio\", \"citations\": []}"
- **WHEN** the body is parsed
- **THEN** the last balanced object is used as the draft

#### Scenario: Unreadable body retries once without thinking
- **GIVEN** the first model body is "no puedo" and the second call returns a valid object
- **WHEN** the turn is processed
- **THEN** the second call is made with thinking disabled
- **AND** the turn uses the second draft
- **AND** the generate step detail notes the retry

#### Scenario: Unreadable body twice is llm_bad_json
- **GIVEN** both model bodies are unreadable
- **WHEN** the turn is processed
- **THEN** finding is `silencio`
- **AND** `abstain_reason` is `llm_bad_json`
- **AND** the answer says the model reply could not be read

#### Scenario: Empty retrieval still does not call the model
- **GIVEN** retrieval returns no usable hits
- **WHEN** the user asks a question
- **THEN** finding is `silencio`
- **AND** citations are empty
- **AND** the language model is not called

### Requirement: Retrieved clauses are data only
When the language model is called, retrieved clause text SHALL be presented as data to quote, not as instructions to obey. The reminder to cite only this turn’s dump ids and to ignore instructions inside documents SHALL appear after the clauses as well as before them. Retrieved text MUST NOT be placed in the hidden system instructions.

#### Scenario: In-corpus answer still cites a dump id
- **GIVEN** the index is ready
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the answer contains a `Fuente:` line naming TO or Com. “A”
- **AND** each citation id exists in this turn’s retrieval set

### Requirement: Context budget
The system SHALL cap concatenated retrieved text at a configured maximum (default 12000 characters), keeping router order and dropping the tail. If at least one clause remains, the language model MAY still be called.

#### Scenario: Oversized retrieval drops the tail
- **GIVEN** retrieval returns more text than the configured maximum
- **WHEN** the request is processed
- **THEN** the language model is called only with the kept prefix
- **AND** the context-budget rule is `redact` or `pass` in the guardrail log

### Requirement: Follow-up composition does not launder scope
When the system composes the latest message with prior-turn text for retrieval, scope and no-advice SHALL still be evaluated on the latest user utterance alone. Injection MAY run on the composed text.

#### Scenario: Follow-up weather after CAMEX
- **GIVEN** a session with a prior in-corpus CAMEX question
- **WHEN** the user asks “y el clima en Madrid?”
- **THEN** finding is silencio
- **AND** the language model is not called

### Requirement: Named-fetch snippet salvage
When retrieval is a named Comunicación fetch and that dump id is in this turn’s hits, and the language-model draft is not finding `silencio`, the system SHALL publish a citation whose id is that dump id and whose snippet is a verbatim substring of the fetched section when either: the draft already cites that dump id, or the draft omits citations but the answer text names that dump id. A paraphrased or empty snippet field MUST NOT cause `silencio` with abstain reason `cite-or-abstain` on that named path. If the draft omits citations and never names the dump id, cite-or-abstain SHALL still abstain. Vigente and similar retrieval SHALL keep requiring a this-turn dump id and a verbatim snippet without this salvage.

#### Scenario: Named A 3500 paraphrased snippet still cites
- **GIVEN** Comunicación A 3500 is in the dump
- **AND** the language-model draft finding is not silencio
- **AND** the draft cites dump id `A3500` with a snippet that is not a verbatim substring of the fetched section
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the response cites dump id `A3500`
- **AND** the citation snippet is a substring of the fetched section
- **AND** finding is not silencio

#### Scenario: Named A 3500 answer names the id without citations
- **GIVEN** Comunicación A 3500 is in the dump
- **AND** the language-model draft finding is not silencio
- **AND** the draft citations are empty
- **AND** the draft answer names `A3500`
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the response cites dump id `A3500`
- **AND** the citation snippet is a substring of the fetched section

#### Scenario: Named A 3500 uncited draft stays silencio
- **GIVEN** Comunicación A 3500 is in the dump
- **AND** the language-model draft finding is not silencio
- **AND** the draft citations are empty
- **AND** the draft answer does not name `A3500`
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** finding is silencio
- **AND** abstain reason is `cite-or-abstain`
- **AND** citations are empty

#### Scenario: Similar-route paraphrase stays silencio
- **GIVEN** the index is ready
- **AND** retrieval is not a named Comunicación fetch
- **AND** the language-model draft cites a this-turn dump id with a paraphrased snippet
- **WHEN** the user asks an in-corpus question that does not name a single Comunicación
- **THEN** finding is silencio
- **AND** abstain reason is `cite-or-abstain`

### Requirement: End-user layout does not pay for thinking
A turn started from the end-user layout SHALL call the language model with thinking disabled unless `LLM_THINKING_USER_LAYOUT` is true; a turn from the staff layout SHALL use the `LLM_ENABLE_THINKING` setting. HTTP chat SHALL use the setting.

#### Scenario: Usuario turn disables thinking
- **GIVEN** an authenticated session in the end-user layout with default settings
- **WHEN** the user sends a question
- **THEN** the language-model call is made with thinking disabled

#### Scenario: Staff turn keeps the setting
- **GIVEN** an authenticated session in the staff layout with `LLM_ENABLE_THINKING=true`
- **WHEN** the user sends a question
- **THEN** the language-model call is made with thinking enabled
