## ADDED Requirements

### Requirement: Named-fetch snippet salvage
When retrieval is a named Comunicación fetch and that dump id is in this turn’s hits, and the language-model draft is not finding `silencio`, the system SHALL publish a citation whose id is that dump id and whose snippet is a verbatim substring of the fetched section when either: the draft already cites that dump id, or the draft omits citations but the answer text names that dump id. A paraphrased or empty snippet field MUST NOT cause `silencio` with abstain reason `cite-or-abstain` on that named path. If the draft omits citations and never names the dump id, cite-or-abstain SHALL still abstain. Vigente and similar retrieval SHALL keep requiring a this-turn dump id and a verbatim snippet without this salvage.

#### Scenario: Named A 3500 paraphrased snippet still cites
- **GIVEN** Comunicación A 3500 is in the dump
- **AND** the language-model draft finding is not silencio
- **AND** the draft cites dump id `A3500` with a snippet that is not a verbatim substring of the fetched section
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the response cites dump id `A3500`
- **AND** the citation snippet is a substring of the fetched section
- **AND** finding is not silencio

#### Scenario: Named A 3500 answer names the id without citations
- **GIVEN** Comunicación A 3500 is in the dump
- **AND** the language-model draft finding is not silencio
- **AND** the draft citations are empty
- **AND** the draft answer names `A3500`
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the response cites dump id `A3500`
- **AND** the citation snippet is a substring of the fetched section

#### Scenario: Named A 3500 uncited draft stays silencio
- **GIVEN** Comunicación A 3500 is in the dump
- **AND** the language-model draft finding is not silencio
- **AND** the draft citations are empty
- **AND** the draft answer does not name `A3500`
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** finding is silencio
- **AND** abstain reason is `cite-or-abstain`
- **AND** citations are empty

#### Scenario: Similar-route paraphrase stays silencio
- **GIVEN** the index is ready
- **AND** retrieval is not a named Comunicación fetch
- **AND** the language-model draft cites a this-turn dump id with a paraphrased snippet
- **WHEN** the user asks an in-corpus question that does not name a single Comunicación
- **THEN** finding is silencio
- **AND** abstain reason is `cite-or-abstain`
