## Purpose

Give operators a live and durable view of one-time ingest and refresh: how many documents the run will process, how many it has already processed, and the date and name of the document currently in flight.

## ADDED Requirements

### Requirement: Console and file progress
One-time ingest and refresh SHALL emit the same progress information to the process console and to a log file on the dump host. The file SHALL remain readable after the process exits. The system MUST NOT require a separate operator command to produce these logs.

#### Scenario: Console shows progress during one-time ingest
- **GIVEN** an empty dump and a CAMEX catalog that lists at least one Comunicación A
- **WHEN** one-time ingest runs
- **THEN** the console shows how many documents this run needs to process
- **AND** the console shows how many documents this run has already processed
- **AND** the console shows the date and name of the document currently being processed

#### Scenario: File keeps progress after the process exits
- **GIVEN** one-time ingest or refresh has finished
- **WHEN** an operator reads the dump-host log file
- **THEN** that file contains the same total, processed count, and current-document date and name that the console showed
- **AND** those lines are still present after the process has exited

#### Scenario: Refresh uses the same progress logs
- **GIVEN** a complete dump whose `last_refresh` is set
- **AND** the catalog lists a new Comunicación A
- **WHEN** refresh runs
- **THEN** the console and the log file show the total for this refresh, the processed count, and the date and name of the document currently being processed

### Requirement: Progress fields for the current run
At the start of one-time ingest or refresh, the system SHALL log the number of documents this run needs to process (the Comunicaciones A in scope for that mode plus the texto ordenado). While a document is being processed, the system SHALL log that document’s name and, when known, its issue date. After the system finishes considering a document, the system SHALL log how many documents this run has already processed. An unchanged or skipped document SHALL still increment that processed count.

#### Scenario: Total is known before the first document
- **GIVEN** a catalog of three unique CAMEX Comunicaciones A
- **WHEN** one-time ingest starts on an empty dump
- **THEN** the logs report a total of four documents (those three plus the texto ordenado)
- **AND** that total appears before any document is stored

#### Scenario: Named Com. A shows date and name
- **GIVEN** Comunicación A 13 (CAMEX-1, 1981-03-02) is the document currently being processed
- **WHEN** one-time ingest or refresh handles that document
- **THEN** the logs include the name A 13 (and its title when the catalog has one)
- **AND** the logs include the issue date 1981-03-02

#### Scenario: Texto ordenado is named while in flight
- **GIVEN** the current Exterior y Cambios texto ordenado is the document currently being processed
- **WHEN** one-time ingest or refresh handles it
- **THEN** the logs name it as the texto ordenado Exterior y Cambios

#### Scenario: Processed count includes skips
- **GIVEN** a dump that already holds a checkpointed Comunicación A whose checksum is unchanged
- **WHEN** one-time ingest or refresh considers that document and skips re-download
- **THEN** the processed count still advances
- **AND** the logs still name that document and, when known, its issue date
