## MODIFIED Requirements

### Requirement: Truncated extract without punto
If the user names a Comunicación without a punto, the system SHALL return an extract of that document in document order, bounded by `CONTEXT_CHUNK_CHARS`, not an entire texto ordenado.

#### Scenario: Named A without punto is truncated
- **GIVEN** Comunicación A 3500 is in the dump
- **WHEN** the user asks what A 3500 says with no punto
- **THEN** the body is an ordered extract of at most `CONTEXT_CHUNK_CHARS` characters, not the full texto ordenado

## ADDED Requirements

### Requirement: Named sections are ordered and punto-scoped
A fetched named section SHALL assemble that document's chunks in document order: by the `ordinal` recorded at ingest when every chunk has one, otherwise by numeric punto then ingest order. When the question names a punto, the section SHALL contain that punto and its sub-puntos plus one neighbouring chunk on each side; when the punto is not found, the whole ordered document is used. The section SHALL be capped at `CONTEXT_CHUNK_CHARS`. Ingest SHALL record an `ordinal` on every chunk.

#### Scenario: Punto with sub-puntos and neighbours
- **GIVEN** `A3500` has chunks with puntos 1, 2, 2.1, 2.2, 3, 4 in that order
- **WHEN** the user asks about punto 2 of A 3500
- **THEN** the fetched section contains puntos 1, 2, 2.1, 2.2 and 3, in that order
- **AND** it does not contain punto 4

#### Scenario: Whole document in order when punto is missing
- **GIVEN** `A3500` has chunks with puntos 1, 2, 3 stored out of order
- **WHEN** the user asks about punto 9.9.9 of A 3500
- **THEN** the fetched section is puntos 1, 2, 3 in that order

#### Scenario: Ingest records ordinals
- **GIVEN** a document is ingested
- **WHEN** its chunks are stored
- **THEN** each chunk has an integer `ordinal` starting at 0 in document order
