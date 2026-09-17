## MODIFIED Requirements

### Requirement: Session memory
The system SHALL keep the last six messages (three exchanges) per session id. If the client omits session id, the system SHALL mint one. The prompt for a turn SHALL include the last two exchanges of that session as prior conversation that is explicitly marked as context and not a citation source; each remembered message is truncated to 300 characters. Follow-up questions SHALL still retrieve from the dump; memory MUST NOT invent a circular: citations keep requiring a dump id retrieved this turn and an anchored snippet. When the latest message starts with a follow-up prefix (`y`, `and`, `ese`, `esa`, `eso`, `that`, `el punto`) or has three words or fewer and names no Comunicación, the retrieval query SHALL be the previous user question followed by the latest message. Idle sessions SHOULD expire after one hour.

#### Scenario: Follow-up still cites the dump
- **GIVEN** the user asked about punto 3.8.5 and received a cited answer
- **WHEN** the user asks “y ese punto?” in the same session
- **THEN** the new answer includes a citation that exists in the dump

#### Scenario: Prior exchange reaches the prompt as context
- **GIVEN** the user asked "qué se exige para liquidar exportaciones" and received the answer "Los residentes deberán liquidar…"
- **WHEN** the user asks "¿cuánto plazo?" in the same session
- **THEN** the language-model prompt contains "Conversación previa (contexto, no fuente"
- **AND** it contains "Usuario: qué se exige para liquidar exportaciones"
- **AND** it contains "Asistente: Los residentes deberán liquidar"
- **AND** the retrieval query is "qué se exige para liquidar exportaciones\n¿cuánto plazo?"

#### Scenario: Short question naming a Comunicación is not composed
- **GIVEN** a session with a prior in-corpus question
- **WHEN** the user asks "Comunicación A 3500?"
- **THEN** the retrieval query is the latest message alone
- **AND** the named fetch runs for A3500

#### Scenario: Cleared session has no prior conversation
- **GIVEN** the user cleared the session
- **WHEN** the user asks a new question
- **THEN** the prompt contains no "Conversación previa" block

## ADDED Requirements

### Requirement: Turn phases are reported
While answering, the system SHALL report the phases `retrieve` (before routing and retrieval), `generate` (before the language-model call) and `verify` (before the output guardrails) through an optional callback supplied by the caller. A callback error MUST NOT fail the turn. Paths that skip a phase (blocked input, empty retrieval, index not ready) SHALL NOT report it.

#### Scenario: Cited answer reports three phases
- **GIVEN** a ready index and a language model that answers
- **WHEN** an in-corpus question runs with a phase callback
- **THEN** the callback receives `retrieve`, `generate`, `verify` in that order

#### Scenario: Blocked input reports no phase
- **GIVEN** an out-of-scope question
- **WHEN** it runs with a phase callback
- **THEN** the callback is not called
