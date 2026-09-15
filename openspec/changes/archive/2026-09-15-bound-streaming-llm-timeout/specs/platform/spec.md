## MODIFIED Requirements

### Requirement: Language-model timeout
The system SHALL bound a language-model call with a configured timeout (default 60 seconds). That bound SHALL be wall-clock for the whole call, including while a streaming thinking trace is still arriving. On timeout the turn SHALL be silencio with abstain reason that the model was unavailable, citations SHALL be empty, and the serving process SHALL still return a structured chat response. The system MUST NOT invent CAMEX text from a partial stream.

#### Scenario: Timed-out generation is silencio
- **GIVEN** the language-model call exceeds the configured timeout
- **WHEN** the request is processed
- **THEN** finding is silencio
- **AND** citations are empty

#### Scenario: Thinking tokens past the bound still silencio
- **GIVEN** the language-model provider keeps sending thinking tokens past the configured timeout
- **WHEN** the request is processed
- **THEN** finding is silencio
- **AND** citations are empty
- **AND** the serving process still returns a structured chat response
