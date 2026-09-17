## MODIFIED Requirements

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

## ADDED Requirements

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
