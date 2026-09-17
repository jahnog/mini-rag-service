## MODIFIED Requirements

### Requirement: Scope
The system SHALL block questions outside BCRA CAMEX / Argentine FX regulation, including weather questions in English, Spanish, or German (`Wetter`). Scope SHALL be evaluated on the latest user utterance, not on prior-turn text composed for retrieval. An off-topic denylist hit on that utterance SHALL block even if the same utterance also contains a CAMEX keyword. Follow-ups that match the session prefix (`y`, `and`, `ese`, …), or that are three words or fewer, name no Comunicación and were composed with the previous question of the same session, and are not on the off-topic denylist SHALL pass scope so retrieval can use the composed query. The token `punto` alone SHALL NOT make a standalone utterance in scope. Blocked turns SHALL name the scope rule in the guardrail log, SHALL use finding `silencio`, SHALL NOT retrieve, and SHALL NOT call the language model.

#### Scenario: Weather is out of scope
- **GIVEN** the user asks about the weather in Madrid
- **WHEN** the request is processed
- **THEN** the scope rule is `block`
- **AND** finding is silencio
- **AND** the language model is not called

#### Scenario: German weather is out of scope
- **GIVEN** the user asks “Wie ist das Wetter in Madrid?”
- **WHEN** the request is processed
- **THEN** the scope rule is `block`
- **AND** the language model is not called

#### Scenario: Weather with a CAMEX keyword is still out of scope
- **GIVEN** the user asks about the weather in Madrid and also names BCRA
- **WHEN** the request is processed
- **THEN** the scope rule is `block`
- **AND** the language model is not called

#### Scenario: Follow-up weather after a CAMEX turn is still out of scope
- **GIVEN** a session with a prior in-corpus CAMEX question
- **WHEN** the user asks “y el clima en Madrid?”
- **THEN** the scope rule is `block`
- **AND** the language model is not called

#### Scenario: Short follow-up in a session passes scope
- **GIVEN** a session with a prior in-corpus CAMEX question
- **WHEN** the user asks "¿cuánto plazo?"
- **THEN** the scope rule is `pass` with detail "in-session follow-up"
- **AND** retrieval uses the composed query

#### Scenario: Short question without a session is blocked
- **GIVEN** no prior question in the session
- **WHEN** the user asks "¿cuánto plazo?"
- **THEN** the scope rule is `block`

