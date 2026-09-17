## MODIFIED Requirements

### Requirement: Language-model timeout
The system SHALL bound a language-model call with a configured timeout (default 60 seconds). That bound SHALL be wall-clock for the whole call, including while a streaming thinking trace is still arriving and including any retry. On timeout the turn SHALL be silencio with abstain reason `llm_timeout`, citations SHALL be empty, the answer SHALL be a Spanish sentence saying the model took too long, and the serving process SHALL still return a structured chat response. The system MUST NOT invent CAMEX text from a partial stream.

#### Scenario: Timed-out generation is silencio
- **GIVEN** the language-model call exceeds the configured timeout
- **WHEN** the request is processed
- **THEN** finding is silencio
- **AND** `abstain_reason` is `llm_timeout`
- **AND** citations are empty

#### Scenario: Thinking tokens past the bound still silencio
- **GIVEN** the language-model provider keeps sending thinking tokens past the configured timeout
- **WHEN** the request is processed
- **THEN** finding is silencio
- **AND** citations are empty
- **AND** the serving process still returns a structured chat response

## ADDED Requirements

### Requirement: Language-model generation settings
The system SHALL expose generation controls as settings: `LLM_TEMPERATURE` (default 0.1, 0–2), `LLM_MAX_TOKENS` (default 1500, at least 64), `LLM_SEED` (unset by default), `LLM_REASONING_BUDGET` (default 0 meaning provider default; sent to the provider only when greater than 0 and never to x.ai hosts) and `LLM_THINKING_USER_LAYOUT` (default false). Every language-model call SHALL send temperature and max tokens; it SHALL send the seed only when set. A call MAY override the thinking flag per turn; when no override is given the `LLM_ENABLE_THINKING` setting applies.

#### Scenario: Defaults reach the provider
- **GIVEN** default settings against a local provider
- **WHEN** a turn calls the language model
- **THEN** the request carries temperature 0.1 and max tokens 1500
- **AND** it carries no seed and no reasoning budget

#### Scenario: Budget and seed when configured
- **GIVEN** `LLM_SEED=7` and `LLM_REASONING_BUDGET=512` against a local provider
- **WHEN** a turn calls the language model
- **THEN** the request carries seed 7
- **AND** the provider extra body carries reasoning budget 512

#### Scenario: Per-call thinking override wins
- **GIVEN** `LLM_ENABLE_THINKING=true`
- **WHEN** a call is made with thinking overridden to off
- **THEN** the provider extra body has thinking disabled for that call only
