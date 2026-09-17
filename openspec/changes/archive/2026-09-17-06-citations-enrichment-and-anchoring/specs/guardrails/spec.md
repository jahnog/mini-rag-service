## MODIFIED Requirements

### Requirement: Cite or abstain
A non-abstain answer MUST include at least one citation the language model produced for this turn whose id exists in this turn’s retrieved dump documents (Comunicación or texto ordenado id, not an internal chunk id) and whose quoted span anchors in that retrieved text. A span anchors when it is a non-empty whitespace-normalized substring of the retrieved text, or when the longest verbatim run of that span found in the retrieved text is at least 40 characters or at least 60% of the span; in the second case the system SHALL replace the citation snippet with that verbatim run and the cite-or-abstain verdict SHALL be `warn` with detail "cita ajustada (<n>)". Retrieved hits MUST NOT be copied in as citations to satisfy this rule. An empty quoted span SHALL fail. Otherwise the system SHALL force finding `silencio` and empty citations and MUST NOT show the draft.

#### Scenario: Missing citation becomes silencio
- **GIVEN** generation would answer without a dump id retrieved this turn
- **WHEN** the response is finalized
- **THEN** finding is silencio
- **AND** citations are empty

#### Scenario: Quote not in the cited document becomes silencio
- **GIVEN** generation cites a dump id retrieved this turn with a quote whose longest verbatim run in that document is under 40 characters and under 60% of the quote
- **WHEN** the response is finalized
- **THEN** finding is silencio
- **AND** citations are empty

#### Scenario: Near-verbatim quote is anchored
- **GIVEN** the retrieved text contains "Los residentes deberán liquidar el cobro de exportaciones en el mercado de cambios."
- **AND** generation cites that dump id with the snippet "Los residentes deben liquidar el cobro de exportaciones en el mercado de cambios"
- **WHEN** the response is finalized
- **THEN** the citation snippet is "liquidar el cobro de exportaciones en el mercado de cambios"
- **AND** the cite-or-abstain verdict is `warn` with detail "cita ajustada (1)"
- **AND** finding is not silencio

#### Scenario: Empty quote becomes silencio
- **GIVEN** generation cites a dump id retrieved this turn with an empty quote
- **WHEN** the response is finalized
- **THEN** finding is silencio
- **AND** citations are empty

#### Scenario: Model omits citations becomes silencio
- **GIVEN** retrieval returned dump hits
- **AND** generation returns an answer with no usable citation ids
- **WHEN** the response is finalized
- **THEN** finding is silencio
- **AND** citations are empty
- **AND** the draft is not shown
