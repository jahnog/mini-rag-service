## Purpose

Keep the official CAMEX dump resumable: store each fetched document on disk before the serving index is written, skip unchanged downloads, and do not treat a dump-only row as a finished one-time ingest.

## ADDED Requirements

### Requirement: Dump checkpoint before index write
When one-time ingest or refresh stores a new or replaced document, the system SHALL record that document in the dump (raw file, extract, and checksum) after the extract is stored and before the serving-index write. The dump record SHALL distinguish a stored extract from a completed index write. `last_refresh` SHALL remain unset until the one-time or refresh run finishes all documents in scope.

#### Scenario: Crash during index write keeps the dump
- **GIVEN** one-time ingest has stored the texto ordenado extract
- **AND** the serving-index write for that document is interrupted
- **WHEN** an operator inspects the dump
- **THEN** the texto ordenado is present in the dump with its checksum
- **AND** `last_refresh` is unset

#### Scenario: Interrupted first run still refuses refresh
- **GIVEN** dump records exist
- **AND** `last_refresh` is unset
- **WHEN** refresh is invoked
- **THEN** no catalog crawl starts
- **AND** the operator is told to finish one-time ingest first

### Requirement: Skip re-download of dumped checksums
A later ingest or refresh SHALL NOT re-download a document whose dump checksum still matches the stored file. If the dump holds that document and the serving-index write is missing or incomplete, the system SHALL write the serving index from the stored extract and SHALL NOT wipe the dump.

#### Scenario: Resume does not fetch an unchanged PDF
- **GIVEN** the texto ordenado PDF and extract are stored with a dump checksum
- **AND** the serving-index write did not complete
- **WHEN** one-time ingest runs again
- **THEN** the texto ordenado is not re-downloaded from BCRA
- **AND** the serving index contains that document
- **AND** the dump is not wiped

#### Scenario: Orphan extract is not re-downloaded
- **GIVEN** a raw PDF and extract on disk whose checksum is not yet in the dump record
- **WHEN** one-time ingest runs
- **THEN** that PDF is not re-downloaded
- **AND** the dump record is written
- **AND** the serving index contains that document

#### Scenario: Legacy complete dump is not re-indexed
- **GIVEN** a dump record written when checksums were only stored after a successful index write
- **AND** that checksum still matches
- **AND** the serving index already contains that id
- **WHEN** one-time ingest or refresh considers the document
- **THEN** that id is not re-downloaded
- **AND** the serving index is not rebuilt for that id
