## ADDED Requirements

### Requirement: Optional trace collector
The serving process MAY export per-turn traces to a collector endpoint when that endpoint is configured. Export MUST fail open: a collector error MUST NOT fail chat. When the endpoint is unset, the process SHALL still answer. Default automated tests MUST NOT require a live collector.

#### Scenario: Unset collector still answers
- **GIVEN** no collector endpoint is configured
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned

### Requirement: Language-model timeout
The system SHALL bound a language-model call with a configured timeout (default 60 seconds). On timeout the turn SHALL be silencio with abstain reason that the model was unavailable, and MUST NOT invent CAMEX text.

#### Scenario: Timed-out generation is silencio
- **GIVEN** the language-model call exceeds the configured timeout
- **WHEN** the request is processed
- **THEN** finding is silencio
- **AND** citations are empty
