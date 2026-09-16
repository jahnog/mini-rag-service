## MODIFIED Requirements

### Requirement: Optional trace collector
The serving process MAY export per-turn traces to a collector endpoint when that endpoint is configured. When the endpoint is set, the process MAY also send a configured API key with those exports. An unset key SHALL still export to an unauthenticated collector. Export MUST fail open: a collector error, including an authentication failure, MUST NOT fail chat. When the endpoint is unset, the process SHALL still answer. Default automated tests MUST NOT require a live collector or a real collector key.

#### Scenario: Unset collector still answers
- **GIVEN** no collector endpoint is configured
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned

#### Scenario: Named Com. A still answers when collector auth fails
- **GIVEN** a collector endpoint is configured
- **AND** the collector rejects the request as unauthenticated
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** a structured chat response is still returned

#### Scenario: Unset key still answers with a collector
- **GIVEN** a collector endpoint is configured
- **AND** no collector API key is configured
- **WHEN** the user asks a vigente question
- **THEN** a structured chat response is still returned

#### Scenario: Clear still works when the collector has a key
- **GIVEN** a collector endpoint is configured
- **AND** a collector API key is configured
- **WHEN** the user sends `/clear`
- **THEN** the acknowledgement has no retrieved citations
- **AND** the language model is not called
