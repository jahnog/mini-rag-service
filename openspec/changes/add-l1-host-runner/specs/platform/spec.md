## ADDED Requirements

### Requirement: Operator dump-host L1
An operator MAY run L1 on the dump host against the same dump and index that chat uses. That command MUST accept the same suite choices as the laptop operator command (retrieval only, generation only, both, and skip the judge). It MUST NOT start the assistant interface.

#### Scenario: Dump-host L1 uses the host dump
- **GIVEN** ingest wrote documents on the host dump
- **AND** the index is ready
- **WHEN** the operator runs L1 on that host
- **THEN** scoring uses that same dump and index
- **AND** the static results document is written

### Requirement: Dump-host L1 serializes with host jobs
Dump-host L1 MUST serialize with ingest and refresh so those jobs do not run at the same time as L1.

#### Scenario: Dump-host L1 does not overlap refresh
- **GIVEN** a scheduled refresh is running
- **WHEN** the operator starts dump-host L1
- **THEN** L1 waits until refresh finishes
- **OR** refresh waits until L1 finishes

#### Scenario: Dump-host L1 does not overlap ingest
- **GIVEN** ingest is running
- **WHEN** the operator starts dump-host L1
- **THEN** L1 waits until ingest finishes
- **OR** ingest waits until L1 finishes

### Requirement: Dump-host L1 stops and reloads serving
Dump-host L1 MUST stop the serving process for the duration of the run. In-process chat sessions MUST NOT survive that stop. After the run finishes or fails, the serving process MUST be running again. After a dump-host operator run, staff Calidad L1 SHALL read the reloaded static document.

#### Scenario: Named Com. A still answers after L1 reload
- **GIVEN** the dump contains Comunicación A 3500
- **AND** a dump-host L1 run has finished and the serving process has reloaded
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** a structured chat response is still returned

#### Scenario: Clear still works after L1 reload
- **GIVEN** a dump-host L1 run has finished and the serving process has reloaded
- **WHEN** the user clicks Clear
- **THEN** Clear is still available
- **AND** the next question does not use turns from before the reload

#### Scenario: Serving is up if L1 fails
- **GIVEN** dump-host L1 has failed
- **WHEN** the operator inspects the host
- **THEN** the serving process is running

## MODIFIED Requirements

### Requirement: Shared dump for refresh and chat
Refresh, chat, and operator L1 on the dump host SHALL read the same dump and index on the host that stores them.

#### Scenario: Same dump for API and refresh
- **GIVEN** ingest wrote documents on the host dump
- **WHEN** the API answers a question
- **THEN** it reads that same dump and index

#### Scenario: Same dump for dump-host L1
- **GIVEN** ingest wrote documents on the host dump
- **AND** the index is ready
- **WHEN** the operator runs L1 on that host
- **THEN** L1 reads that same dump and index
