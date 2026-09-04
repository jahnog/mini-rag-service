# platform Specification

## Purpose

Keep the service operable when the dump is empty, honest about dates, cheap enough to demo, and checked by automated tests without paying for L1 on every change.

## Requirements

### Requirement: Health document
The system SHALL expose `GET /health` that reports last_refresh, to_as_of, last_comm_id, n_docs, and index_ready. It SHOULD also report the embedding model name. When the dump or index is missing, the process SHALL still start and health SHALL return `index_ready` false with HTTP 200. last_refresh, to_as_of, and last_comm_id SHALL still be present (null is allowed). n_docs SHALL still be present (0 is allowed). The system MUST NOT use HTTP 503 solely because the index is empty.

#### Scenario: Empty dump
- **GIVEN** no dump has been ingested
- **WHEN** the service starts
- **THEN** GET /health succeeds with HTTP 200
- **AND** index_ready is false
- **AND** last_refresh, to_as_of, last_comm_id, and n_docs are present

### Requirement: Disclaimer
Every answer and the interface footer SHALL state that the extract is unofficial, not BCRA, not legal advice, and dated as of last_refresh.

#### Scenario: Disclaimer on silencio
- **GIVEN** any chat response
- **WHEN** it is shown
- **THEN** the unofficial-extract wording and last_refresh appear

### Requirement: Message size and k caps
The system SHALL reject a message longer than the configured maximum (default 4000 characters) and SHALL cap retrieval k at the configured maximum (default 8). Oversized messages MUST NOT retrieve, MUST NOT call the language model, and MUST NOT produce invented CAMEX text.

#### Scenario: Oversized message
- **GIVEN** a message longer than the configured maximum
- **WHEN** it is posted
- **THEN** the system rejects it without producing CAMEX clauses
- **AND** the language model is not called

### Requirement: Rate limit
The system SHALL apply a crude per-client rate limit (default 20 chat requests per 60 seconds) and SHALL queue concurrent UI users. Extra requests SHALL be rejected or delayed and MUST NOT each produce a full CAMEX answer. An optional shared demo secret MAY be required when the UI is on a public URL. A local demo MAY leave that secret unset.

#### Scenario: Repeated requests are limited
- **GIVEN** a client that exceeds the configured request rate
- **WHEN** further chat requests are sent
- **THEN** those extra requests are rejected or delayed
- **AND** they do not each produce a full CAMEX answer

### Requirement: Single-process session memory
Chat session memory is in-process. The serving process SHALL run as one worker. v1 MUST NOT serve chat from multiple replicas that do not share that memory.

#### Scenario: Two sessions on one process
- **GIVEN** the chat process is running
- **WHEN** two clients use different session ids at the same time
- **THEN** each session keeps its own last turns
- **AND** one session’s `/clear` does not wipe the other

### Requirement: Automated tests with fakes
The project SHALL provide a test command that runs unit and acceptance tests with fakes (no live LLM key required for L1) and SHALL emit a coverage report for the deterministic core.

#### Scenario: Default test command
- **GIVEN** the repository test command
- **WHEN** it runs
- **THEN** unit and Gherkin suites execute with fakes
- **AND** a coverage report file is produced

### Requirement: Shared dump for refresh and chat
Refresh and chat SHALL read the same dump and index on the host that stores them.

#### Scenario: Same dump for API and refresh
- **GIVEN** ingest wrote documents on the host dump
- **WHEN** the API answers a question
- **THEN** it reads that same dump and index
