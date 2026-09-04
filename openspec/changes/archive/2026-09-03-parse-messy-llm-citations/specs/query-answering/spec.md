## ADDED Requirements

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
