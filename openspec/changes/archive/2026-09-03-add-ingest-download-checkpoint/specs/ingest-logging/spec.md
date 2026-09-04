## Purpose

Show operators when a document is actually downloaded and when it has been stored and indexed, without treating checksum skips as downloads.

## ADDED Requirements

### Requirement: Download and index progress
When one-time ingest or refresh fetches a document from BCRA, the system SHALL log that the download started (document id, name, issue date when known, and source URL) to the process console and to the dump-host log file. After the dump stores that document’s extract and checksum, the system SHALL log that the dump checkpoint was written (document id and checksum). After the serving-index write for that document succeeds, the system SHALL log that the document was indexed (document id). An unchanged skip SHALL NOT emit those download or index lines for that document.

#### Scenario: New Comunicación logs download and index
- **GIVEN** an empty dump and Comunicación A 13 (CAMEX-1, 1981-03-02) in the catalog
- **WHEN** one-time ingest fetches and stores A 13
- **THEN** the console and the log file show that download of A 13 started, including its title and issue date 1981-03-02 and its source URL
- **AND** they show that A 13 was dump-checkpointed
- **AND** they show that A 13 was indexed

#### Scenario: Unchanged id does not log a download
- **GIVEN** a dump whose checksum for A 13 still matches
- **AND** the serving index already contains A 13
- **WHEN** one-time ingest considers A 13 and skips re-download
- **THEN** the logs do not claim that A 13 was downloaded
- **AND** the processed count still advances
