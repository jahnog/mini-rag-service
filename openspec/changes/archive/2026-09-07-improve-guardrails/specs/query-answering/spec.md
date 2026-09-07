## ADDED Requirements

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
