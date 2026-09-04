## Purpose

Give an operator a repeatable way to install and update the CAMEX assistant on the dump host so chat, ingest, and refresh share one persistent store, without hosting language or embedding models on that host.

## ADDED Requirements

### Requirement: SSH deploy and update
The system SHALL provide an operator command that copies the application to a configured remote host over SSH and installs a serving process that starts on boot and restarts on failure. A second run SHALL update application code and process config without deleting the dump, the index, or existing secrets. Documented operator commands SHALL include that update command.

#### Scenario: First deploy starts an empty serving process
- **GIVEN** the remote host has no prior dump
- **WHEN** the operator runs the deploy command and fills required secrets
- **THEN** the serving process is installed and running
- **AND** GET /health succeeds with HTTP 200
- **AND** index_ready is false
- **AND** last_refresh, to_as_of, last_comm_id, and n_docs are present

#### Scenario: Second deploy keeps the dump
- **GIVEN** the remote host already holds a dump and index from a prior ingest
- **WHEN** the operator runs the deploy command again
- **THEN** application code and process config are updated
- **AND** the dump and index are still present
- **AND** existing secrets are not replaced

### Requirement: One worker on the dump host
The serving process SHALL run as a single worker. v1 MUST NOT start multiple serving replicas on that host.

#### Scenario: Serving process has one worker
- **GIVEN** a successful deploy
- **WHEN** the serving process is inspected
- **THEN** it is configured as one worker
- **AND** it is not started as multiple replicas

### Requirement: Persistent host dump
Ingest, refresh, and chat SHALL use the same directory on the remote host. Deploy MUST NOT wipe that directory. Until ingest has completed, GET /health SHALL still return HTTP 200 with index_ready false. A chat request MUST NOT invent CAMEX clauses while the index is not ready (finding silencio).

#### Scenario: Chat before ingest is silencio
- **GIVEN** deploy succeeded and no dump has been ingested
- **WHEN** a client posts a CAMEX question
- **THEN** the answer is silencio
- **AND** no CAMEX clause is invented
- **AND** the language model is not required to produce that silencio

#### Scenario: Same dump for ingest, refresh, and chat
- **GIVEN** ingest wrote documents on the host dump
- **WHEN** refresh runs and the API answers a question
- **THEN** both read that same dump and index

### Requirement: Scheduled refresh and on-demand jobs
The dump host SHALL run refresh on a daily schedule. The operator SHALL be able to start ingest and refresh as one-shot host jobs. Those jobs SHALL NOT run concurrently with the serving process. Refresh MUST refuse until one-time ingest has set last_refresh. After a job finishes or fails, the serving process SHALL be running again.

#### Scenario: Daily refresh after a completed ingest
- **GIVEN** last_refresh is set on the host dump
- **WHEN** the scheduled refresh runs
- **THEN** the serving process is stopped for the job
- **AND** refresh appends new catalog ids or replaces the texto ordenado only when its checksum changed
- **AND** the serving process is running after the job

#### Scenario: Refresh refuses an incomplete dump
- **GIVEN** last_refresh is unset
- **WHEN** refresh is started
- **THEN** it exits without crawling the catalog
- **AND** the serving process is running afterwards

#### Scenario: On-demand ingest
- **GIVEN** the serving process is installed
- **WHEN** the operator starts the one-shot ingest job
- **THEN** ingest runs on the host dump
- **AND** the serving process is not concurrent with that job
- **AND** the serving process is running after the job

### Requirement: Remote model endpoints
Chat SHALL use the configured language-model settings. Index upsert and similarity search SHALL use the configured embedding base URL, which MAY be a host other than the dump host. Deploy MUST NOT install an embedding or chat model on the dump host.

#### Scenario: Embeddings are not on the dump host
- **GIVEN** a deployed serving process
- **WHEN** ingest upserts or chat performs similarity search
- **THEN** embedding requests go to the configured remote embedding endpoint
- **AND** no embedding model is installed on the dump host

#### Scenario: Chat uses the configured language model
- **GIVEN** a ready index and a configured language-model key
- **WHEN** an in-corpus question is answered
- **THEN** the language-model call uses the configured remote chat endpoint
- **AND** no chat model is installed on the dump host

### Requirement: Empty-dump start
After a successful deploy and before ingest, the serving process SHALL start. The process MUST NOT fail solely because the dump or index is missing.

#### Scenario: Process starts with no dump
- **GIVEN** the dump directory is empty
- **WHEN** deploy enables the serving process
- **THEN** the process is running
- **AND** GET /health returns HTTP 200 with index_ready false
