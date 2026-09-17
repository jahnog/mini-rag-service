## MODIFIED Requirements

### Requirement: Freeze honesty
The system SHALL NOT claim “normativa vigente hoy” without qualifying the dump freeze. A draft names the freeze when it contains `to_as_of` and either the full `last_refresh` value or its calendar date. If the draft was unqualified, the system SHALL append the Spanish freeze sentence "Según el dump del <fecha> (texto ordenado al <to_as_of>)." and the freeze-honesty verdict SHALL be `warn`. If the draft already named the freeze, the verdict SHALL be `pass`. The same dates SHALL appear on the health document and the UI banner.

#### Scenario: Vigente wording is qualified
- **GIVEN** last_refresh is 2026-09-01T00:00:00+00:00 and to_as_of is A8307
- **AND** the draft says "Esta es la normativa vigente hoy."
- **WHEN** the freeze-honesty rail runs
- **THEN** the verdict is `warn`
- **AND** the answer ends with "Según el dump del 2026-09-01 (texto ordenado al A8307)."

#### Scenario: Date form already present passes
- **GIVEN** last_refresh is 2026-09-01T00:00:00+00:00 and to_as_of is A8307
- **AND** the draft says "Según el dump del 2026-09-01 (texto ordenado al A8307), los residentes deberán liquidar."
- **WHEN** the freeze-honesty rail runs
- **THEN** the verdict is `pass`
- **AND** the answer is unchanged

## ADDED Requirements

### Requirement: Prompt leak fingerprints both prompt languages
The prompt-leak rail SHALL block an answer containing the turn delimiter or any system-prompt fingerprint, and the fingerprint set SHALL include verbatim sentences from both the legacy English and the current Spanish system prompt.

#### Scenario: Spanish fingerprint leaks
- **GIVEN** the answer contains "Respondé solo con un objeto JSON con las claves answer, finding y citations."
- **WHEN** the prompt-leak rail runs
- **THEN** the verdict is `block` with detail "system prompt fingerprint"

#### Scenario: English fingerprint still leaks
- **GIVEN** the answer contains "Respond only with JSON keys answer, finding, citations."
- **WHEN** the prompt-leak rail runs
- **THEN** the verdict is `block`
