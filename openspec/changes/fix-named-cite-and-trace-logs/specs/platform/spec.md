## ADDED Requirements

### Requirement: Local traces alongside optional collector
The serving process MAY export per-turn traces to a collector endpoint when that endpoint is configured. Export MUST fail open: a collector error MUST NOT fail chat. Whether or not that endpoint is set, the process SHALL also write compact per-span records to a dump-host traces file. A failure to write that file MUST NOT fail chat. Default automated tests MUST NOT require a live collector.

#### Scenario: Unset collector still answers and still writes local traces
- **GIVEN** no collector endpoint is configured
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned
- **AND** the dump-host traces file includes a `chat.turn` record

#### Scenario: Collector error still answers
- **GIVEN** a collector endpoint is configured
- **AND** export to that collector fails
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned
- **AND** the dump-host traces file still includes a `chat.turn` record
