## MODIFIED Requirements

### Requirement: Named Comunicación fetch
When the user names a Comunicación “A” by number, the system SHALL fetch that document if it is in the dump, and SHALL return silencio if it is not. Named lookup SHALL take precedence over vigente intent. When the response cites that Comunicación, the citation id SHALL be the dump document id (for example A3500), not an internal chunk id. When that Comunicación is in the dump and the language-model draft is not silencio and already names that dump id (as a citation id or in the answer), the response SHALL cite that dump id even if the model’s snippet field is paraphrased or empty; the published snippet SHALL be a verbatim substring of the fetched section.

#### Scenario: A 3500 is in the dump
- **GIVEN** Comunicación A 3500 is in the manifest
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the response cites A 3500
- **AND** the citation id is the dump id A3500

#### Scenario: Named A 3500 paraphrased snippet still cites
- **GIVEN** Comunicación A 3500 is in the manifest
- **AND** the language-model draft cites `A3500` with a paraphrased snippet
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the response cites dump id `A3500`
- **AND** finding is not silencio

#### Scenario: Invented Comunicación is silencio
- **GIVEN** Comunicación A 9999 is not in the manifest
- **WHEN** the user asks what Comunicación A 9999 says
- **THEN** finding is silencio
- **AND** citations are empty
- **AND** the answer names `last_refresh`
