## Purpose

Load the official BCRA CAMEX Comunicaciones “A” plus the Exterior y Cambios texto ordenado into a living dump and serving index, then keep that dump current with a separate refresh operation.

## ADDED Requirements

### Requirement: Official CAMEX A catalog
The system SHALL ingest each unique Comunicación “A” that the BCRA communications search associates with circular CAMEX, from the founding CAMEX-1 document through the latest listed id.

#### Scenario: Catalog is CAMEX A only
- **GIVEN** the official BCRA communications search
- **WHEN** one-time ingest runs
- **THEN** every stored comunicación is tipo A and tagged CAMEX
- **AND** duplicate catalog rows for the same id collapse to one stored document

#### Scenario: Founding circular is included
- **GIVEN** Comunicación A 13 (CAMEX-1, 1981-03-02) is listed
- **WHEN** one-time ingest completes
- **THEN** A 13 is present in the dump manifest

#### Scenario: Latest listed id is included
- **GIVEN** the official BCRA communications search whose newest CAMEX A id is A 8464
- **WHEN** one-time ingest completes
- **THEN** A 8464 is present in the dump manifest

### Requirement: No foreign corpora
The system SHALL NOT ingest documents from hosts other than bcra.gob.ar, including Banxico or other central banks.

#### Scenario: Non-BCRA host is rejected
- **GIVEN** a candidate URL on a non-bcra.gob.ar host
- **WHEN** ingest or refresh runs
- **THEN** that document is not stored

### Requirement: Texto ordenado as clause store
The system SHALL ingest the current official texto ordenado on Exterior y Cambios and SHALL record the last Comunicación incorporated into that texto ordenado as `to_as_of`.

#### Scenario: TO header is recorded
- **GIVEN** the official Exterior y Cambios texto ordenado whose header names a last incorporated Comunicación
- **WHEN** one-time ingest completes
- **THEN** the dump manifest exposes that `to_as_of` value

#### Scenario: TO header is recorded after refresh replace
- **GIVEN** a stored texto ordenado whose checksum no longer matches
- **AND** the new header names a later incorporated Comunicación
- **WHEN** refresh completes
- **THEN** the dump manifest `to_as_of` matches that header

### Requirement: Full text for substantive A’s
The system SHALL store full text for every CAMEX Comunicación A that is not a texto-ordenado reprint pack, including those titled Adecuaciones. If a title looks like both an Adecuación and a reprint pack, the reprint-pack rule wins and only a short event record is stored.

#### Scenario: Adecuaciones are kept in full
- **GIVEN** a CAMEX A whose title is an Adecuación and whose body states a new rule
- **WHEN** ingest processes it
- **THEN** the full extract is stored, not only the header

#### Scenario: Post-TO A’s stay full text
- **GIVEN** a CAMEX A whose issue date is after `to_as_of`
- **WHEN** ingest or refresh stores it
- **THEN** the full extract is stored so later answers can treat it as post-texto-ordenado

### Requirement: Event record for TO reprints
The system SHALL store only a short event record (header, reference, and a brief body) for documents that are texto-ordenado reprint packs (“actualización del texto ordenado” / replacement sheets).

#### Scenario: TO reprint is an event
- **GIVEN** a CAMEX A that only attaches replacement sheets of the texto ordenado
- **WHEN** ingest processes it
- **THEN** the dump holds a short event record
- **AND** the full texto ordenado is not duplicated from that annex

### Requirement: Empty-dump bootstrap
The system SHALL provide a one-time ingest operation that, from an empty dump, stores the CAMEX A catalog, the current texto ordenado, and a serving index. One-time ingest SHALL set `last_refresh`, `to_as_of`, and `last_comm_id` when that first run completes.

#### Scenario: Empty dump is filled
- **GIVEN** no dump has been ingested
- **WHEN** one-time ingest completes
- **THEN** the dump manifest lists the catalog ids and the texto ordenado
- **AND** `last_refresh` is set
- **AND** `to_as_of` is set from the texto ordenado header
- **AND** `last_comm_id` is the highest stored Comunicación A id

### Requirement: One-time ingest resumes and does not wipe
If the dump already has successful checkpoints and `last_refresh` is unset, one-time ingest SHALL resume remaining work and SHALL NOT wipe stored documents. Completing that resumed first run SHALL set `last_refresh` and `last_comm_id`. If `last_refresh` is already set, one-time ingest SHALL NOT fetch CAMEX A ids that are not yet in the dump manifest; the operator MUST run refresh for those ids. Unchanged checksums SHALL NOT be re-downloaded.

#### Scenario: Resume after interruption
- **GIVEN** one-time ingest stopped after 400 documents were checkpointed
- **AND** `last_refresh` is unset
- **WHEN** one-time ingest runs again
- **THEN** those 400 ids are not re-downloaded if their checksum is unchanged
- **AND** remaining ids continue from the catalog
- **AND** when the run completes, `last_refresh` and `last_comm_id` are set

#### Scenario: One-time ingest does not wipe
- **GIVEN** a dump that already holds checkpointed documents
- **WHEN** one-time ingest runs again
- **THEN** those documents remain

#### Scenario: Completed one-time ingest does not pull new catalog ids
- **GIVEN** a complete dump whose latest id is A 8464 and whose `last_refresh` is set
- **AND** the BCRA search lists A 8465
- **WHEN** one-time ingest runs again
- **THEN** A 8465 is not stored
- **AND** unchanged checksums are not re-downloaded

#### Scenario: Unchanged complete dump is not re-fetched
- **GIVEN** a complete dump whose checksums still match
- **AND** `last_refresh` is set
- **WHEN** one-time ingest runs again
- **THEN** no BCRA download occurs for those unchanged ids
- **AND** stored documents are not wiped

### Requirement: Atomic checkpoint
The system SHALL checkpoint a document in the dump manifest only after that document’s extract is stored and its serving-index write succeeds. A later ingest or refresh SHALL skip re-download of ids whose checksum is unchanged. If the dump already holds an id whose serving-index write is missing, ingest or refresh SHALL write that id to the index from the stored extract and SHALL NOT wipe the dump.

#### Scenario: Checkpoint waits for index write
- **GIVEN** an extract that has been stored but whose index write has not succeeded
- **WHEN** ingest or refresh is interrupted
- **THEN** that id is not recorded as a successful checkpoint

#### Scenario: Missing index row is repaired
- **GIVEN** a checkpointed document whose index write failed after a previous bug or crash
- **WHEN** ingest or refresh runs again
- **THEN** the serving index contains that document
- **AND** the dump is not wiped

#### Scenario: Unchanged checksum skips re-download
- **GIVEN** a checkpointed id whose checksum still matches
- **AND** the serving index already contains that id
- **WHEN** ingest or refresh runs
- **THEN** that id is not re-downloaded

### Requirement: Polite download
The system SHALL limit concurrent downloads so the BCRA host is not flooded (a small fixed concurrency and a short delay between requests).

#### Scenario: Concurrent downloads are bounded
- **GIVEN** hundreds of PDFs remain to download
- **WHEN** ingest or refresh runs
- **THEN** the number of simultaneous BCRA requests stays within the configured small bound

### Requirement: Refresh appends new documents
The system SHALL provide a refresh operation that appends CAMEX A documents not yet in the dump manifest. Refresh SHALL run on the machine that holds the dump. Each successful refresh SHALL set `last_refresh` and `last_comm_id`.

#### Scenario: New A after last refresh
- **GIVEN** a dump whose latest id is A 8464 and whose `last_refresh` is set
- **AND** the BCRA search lists A 8465
- **WHEN** refresh runs
- **THEN** A 8465 is downloaded, stored, and checkpointed
- **AND** `last_refresh` and `last_comm_id` update

### Requirement: Refresh replaces TO on checksum change
Refresh SHALL replace the texto ordenado only when that file’s checksum changed. When the checksum matches, existing TO clauses SHALL NOT be rebuilt. When the checksum changed, the dump SHALL record `to_as_of` from the new header and the serving index SHALL contain only the new TO clauses.

#### Scenario: Unchanged TO is skipped
- **GIVEN** the texto ordenado checksum matches the manifest
- **WHEN** refresh runs
- **THEN** existing TO clauses are not rebuilt

#### Scenario: Changed TO updates to_as_of and index
- **GIVEN** a stored TO whose checksum no longer matches
- **AND** the new header names a later incorporated Comunicación
- **WHEN** refresh completes
- **THEN** dump manifest `to_as_of` matches that header
- **AND** TO clauses in the serving index are the new extract

#### Scenario: Punto only in the old TO is gone
- **GIVEN** a TO clause present only in the previously stored texto ordenado
- **AND** refresh replaces the texto ordenado because the checksum changed
- **WHEN** refresh completes
- **THEN** that clause is absent from the serving index

### Requirement: Refresh refuses until one-time has completed
If no successful checkpoint exists, or checkpoints exist but `last_refresh` is unset, refresh SHALL refuse, SHALL NOT start a catalog crawl, and SHALL tell the operator to run one-time ingest.

#### Scenario: Refresh refuses a missing dump
- **GIVEN** no dump has been ingested
- **WHEN** refresh is invoked
- **THEN** no catalog crawl starts
- **AND** the operator is told to run one-time ingest first

#### Scenario: Refresh refuses an empty placeholder dump
- **GIVEN** a dump manifest with no successful checkpoint
- **WHEN** refresh is invoked
- **THEN** no catalog crawl starts
- **AND** the operator is told to run one-time ingest first

#### Scenario: Refresh refuses an interrupted first run
- **GIVEN** checkpointed documents
- **AND** `last_refresh` is unset
- **WHEN** refresh is invoked
- **THEN** no catalog crawl starts
- **AND** the operator is told to finish one-time ingest first

### Requirement: Serving index is complete after success
After a successful one-time ingest or refresh, the serving index on the same host SHALL contain the stored documents, including full extracts and event records.

#### Scenario: Index is ready after one-time ingest
- **GIVEN** no dump has been ingested
- **WHEN** one-time ingest completes
- **THEN** the serving index contains the stored CAMEX A documents and the texto ordenado

#### Scenario: Event records are in the index
- **GIVEN** a CAMEX A stored as a short event record
- **WHEN** one-time ingest or refresh completes
- **THEN** the serving index contains that event record

### Requirement: Serving index upserts only what changed
Refresh SHALL upsert new or replaced documents and SHALL NOT rebuild unchanged documents whose checksum still matches and whose index write already succeeded.

#### Scenario: Index upserts only what changed
- **GIVEN** a dump and index already holding A 8464
- **AND** refresh stores A 8465
- **WHEN** refresh completes
- **THEN** the serving index contains A 8465
- **AND** unchanged documents are not rebuilt

### Requirement: Known catalog hole is documented not filled
The system SHALL NOT crawl untagged A-series documents solely to fill CAMEX sequence numbers missing between 1-232 and 1-314 (1990–97). An operator-facing note SHALL mention that hole.

#### Scenario: No blind A-series crawl
- **GIVEN** CAMEX sequence jumps from 232 to 314 in the official tag
- **WHEN** one-time ingest completes
- **THEN** the dump does not contain arbitrary untagged A ids from 1990–1997 solely to close that jump

#### Scenario: Hole is noted for operators
- **GIVEN** ingest has completed
- **WHEN** an operator reads the dump note
- **THEN** the 1990–97 CAMEX tag hole is mentioned
