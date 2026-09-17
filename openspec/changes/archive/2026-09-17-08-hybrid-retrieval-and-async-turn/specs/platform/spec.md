## ADDED Requirements

### Requirement: Retrieval and health run off the event loop
The serving process SHALL execute the dump-health check and the routing/retrieval step of a chat turn in a worker thread, so a second concurrent turn is not blocked by the first turn's embedding call or index query. The dump manifest SHALL be parsed once per file version (path, modification time, size) and the health document cached per manifest version; a rewritten manifest SHALL be picked up on the next turn without a restart.

#### Scenario: Concurrent turns do not serialize on retrieval
- **GIVEN** an index whose search takes 300 ms
- **WHEN** two chat turns start at the same time
- **THEN** both complete in about 300 ms of retrieval wall time, not 600 ms

#### Scenario: Rewritten manifest refreshes health
- **GIVEN** a cached health document for the current manifest
- **WHEN** the manifest file is rewritten with a new `last_refresh`
- **THEN** the next health document reports the new `last_refresh`
