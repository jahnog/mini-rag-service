## ADDED Requirements

### Requirement: Chunks fit the embedding input limit
The system SHALL index only chunks whose text fits the configured embedding input limit. Strategy B MUST still split on numbered puntos and sections. When a single punto or section exceeds that limit, the system SHALL store multiple chunks for that unit and SHALL keep the same punto identifier on each part. Strategy A MUST still cover documents without clean numbered puntos, including a named historical Comunicación A.

#### Scenario: Oversized punto stays retrievable by number
- **GIVEN** the texto ordenado contains a numbered punto whose text exceeds the configured embedding input limit
- **WHEN** it is indexed
- **THEN** that punto is stored as more than one chunk
- **AND** each of those chunks still identifies the same numbered punto

#### Scenario: Named historical A still indexed
- **GIVEN** a 1983 CAMEX A without clean numbered puntos
- **AND** a passage longer than the configured embedding input limit
- **WHEN** it is indexed
- **THEN** it is still searchable for named-document lookup using strategy A
- **AND** no stored chunk exceeds the configured embedding input limit
