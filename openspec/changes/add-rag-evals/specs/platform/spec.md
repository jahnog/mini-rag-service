## ADDED Requirements

### Requirement: Chat process does not load eval scoring
The serving process SHALL answer chat without loading evaluation scoring or the judge. Optional retriever spans on chat MUST NOT pull in the evaluation operator. Default automated tests MUST NOT require the judge extra for chat.

#### Scenario: Chat without judge extra
- **GIVEN** the judge extra is not installed
- **WHEN** the user asks a named Comunicación A that is in the dump
- **THEN** a structured chat response is still returned

### Requirement: Namespaced eval annotations
When a collector endpoint is configured, an operator L1 run MAY attach scores as annotations on exported spans. Annotation names SHALL be prefixed with the suite (`retrieval.` or `generation.`). A collector error MUST NOT fail the static L1 write. When the endpoint is unset, L1 SHALL still write the static results document. Default automated tests MUST NOT require a live collector.

#### Scenario: Unset collector still writes L1
- **GIVEN** no collector endpoint is configured
- **WHEN** an operator L1 run completes
- **THEN** the static results document is written
- **AND** the run is not treated as failed

#### Scenario: Collector error does not wipe results
- **GIVEN** a collector endpoint is configured
- **AND** the collector rejects annotations
- **WHEN** an operator L1 run finishes scoring
- **THEN** the static results document still contains the scores

#### Scenario: Annotations are namespaced
- **GIVEN** a collector endpoint is configured
- **AND** both suites ran
- **WHEN** annotations are exported
- **THEN** retrieval scores use a `retrieval.` prefix
- **AND** generation scores use a `generation.` prefix

### Requirement: Oracle generation does not search
When generation is scored with oracle context, the serving index MUST NOT be searched for those gold questions. Retriever spans MUST NOT be emitted for that oracle generation. Chat turns that retrieve as usual MAY still export retriever spans when the collector is set.

#### Scenario: Oracle generation has no retriever span
- **GIVEN** a collector endpoint is configured
- **AND** generation context is oracle
- **WHEN** L1 scores a gold question
- **THEN** no retriever search span is exported for that generation
- **AND** a structured generation result is still produced

#### Scenario: Chat retrieve still fail-open
- **GIVEN** a collector endpoint is configured
- **WHEN** the user asks a named Comunicación A that is in the dump
- **THEN** a structured chat response is still returned even if span export fails

## MODIFIED Requirements

### Requirement: Optional trace collector
The serving process MAY export per-turn traces to a collector endpoint when that endpoint is configured. Export MUST fail open: a collector error MUST NOT fail chat. When the endpoint is unset, the process SHALL still answer. When the endpoint is set, retrieval steps MAY be exported as retriever spans that include retrieved document identifiers and truncated document text. Default automated tests MUST NOT require a live collector. Hostnames MUST NOT be hardcoded; the collector URL is configuration.

#### Scenario: Unset collector still answers
- **GIVEN** no collector endpoint is configured
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned

#### Scenario: Retriever spans on chat
- **GIVEN** a collector endpoint is configured
- **WHEN** the user asks what is required today to liquidate
- **THEN** a retriever span MAY be exported for that turn
- **AND** chat still returns a structured response if export fails
