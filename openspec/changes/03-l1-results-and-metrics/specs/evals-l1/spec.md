## MODIFIED Requirements

### Requirement: Published metrics
An L1 run SHALL publish two independent blocks. The retrieval block SHALL include at least: hit@5, precision@5, MRR, NDCG@5, retrieve latency p50 and p95, and (when the judge ran) context precision and context recall. NDCG@5 SHALL be bounded to the closed interval [0, 1]: each gold document id contributes relevance once, at its first rank among the top 5 retrieved ids, even when several retrieved chunks belong to that document. The generation block SHALL include at least: faithfulness and answer relevancy (when the judge ran), citation-id exact match, citation-punto exact when gold puntos exist, citation-snippet grounded (each cited snippet is a substring of the stuffed context), finding exact, generate latency p50 and p95, and the context source (`oracle` or `retrieved`). Citation-id exact SHALL be the headline metric and SHALL compare dump ids the model cited, not retrieved ids. Precision@5 SHALL be gold dump-id overlap in the top 5 retrieved documents and MUST NOT be the same number as context precision (judged chunk relevance). The run SHALL also publish chunking A versus B on the structured slice and a slice table (definición, obligación, silencio, cross-ref, superseded, post-TO patch) whose values are generation citation-id exact when generation ran, otherwise retrieval hit@5. Nested blocks are canonical; flat copies of citation-id exact, hit@5, and MRR MAY exist for older screens. The published document MUST NOT contain a `ragas` key.

#### Scenario: Published results exist after L1
- **GIVEN** an L1 run has completed both suites
- **WHEN** an operator reads the published results
- **THEN** citation-id exact is presented as the headline number
- **AND** it equals the generation block’s citation-id exact
- **AND** hit@5 and A vs B appear with the slice table
- **AND** the retrieval and generation blocks are both present
- **AND** the text states which documents strategy B covered

#### Scenario: Repeated chunks of one gold document do not inflate NDCG
- **GIVEN** a gold row whose only gold id is `texto_ordenado`
- **AND** the top 5 retrieved ids are `texto_ordenado, texto_ordenado, A8359, texto_ordenado, A3500`
- **WHEN** NDCG@5 is scored
- **THEN** the value is 1.0

#### Scenario: NDCG rewards an earlier first hit
- **GIVEN** a gold row whose only gold id is `A3500`
- **AND** the top 5 retrieved ids are `A8359, A3500, A3500, A3500, A3500`
- **WHEN** NDCG@5 is scored
- **THEN** the value equals 1 / log2(3), about 0.631, and never exceeds 1

#### Scenario: Precision@5 is not context precision
- **GIVEN** a completed retrieval suite with the judge
- **WHEN** an operator reads precision@5 and context precision
- **THEN** both numbers are present
- **AND** they are distinct fields

#### Scenario: Citation-id uses model cites
- **GIVEN** retrieval returned gold dump ids
- **AND** generation cited a different set of dump ids
- **WHEN** citation-id exact is scored
- **THEN** the headline uses the generated citations
- **AND** retrieval hit@5 still uses the retrieved ids

#### Scenario: Citation snippet not in context fails grounded
- **GIVEN** a generated citation whose snippet is not in the stuffed context
- **WHEN** citation-snippet grounded is scored for that row
- **THEN** the row scores 0 for that metric

#### Scenario: Superseded-trap gold is sliced
- **GIVEN** gold rows in the superseded bucket
- **WHEN** L1 publishes the slice table
- **THEN** that bucket has a score

### Requirement: Static results file
L1 SHALL write a static results document that the assistant UI reads. The browser MUST NOT compute L1 scores. Refresh MUST NOT run L1 unless the operator opts in. The repository SHALL commit a results document at `evals/l1.json`. That document MAY be a published operator run made on the published dump (the dump that `scripts/publish-data.sh` ships), in which case it carries `unpublished: false` and `sample: false`; otherwise it MUST be labeled unpublished or sample. The UI SHALL label the numbers strictly by those flags. The document MUST mark judged metrics skipped, not zero, when the judge did not run. A collector error, including an authentication failure, MUST NOT fail that static write. The serving process SHALL expose the stored document read-only at `GET /evals/l1`; when no document exists it SHALL return the same unpublished stub the UI renders, with HTTP 200.

#### Scenario: UI reads last run
- **GIVEN** a results file from the last L1 run
- **WHEN** the user opens Calidad L1
- **THEN** those stored numbers are shown
- **AND** no eval model is invoked in the client

#### Scenario: Committed published run is shown as such
- **GIVEN** the committed `evals/l1.json` carries `unpublished: false` and `sample: false`
- **WHEN** the user expands Calidad L1
- **THEN** the numbers are shown without the sample banner

#### Scenario: Shipped placeholder is labeled
- **GIVEN** a results document labeled unpublished or sample
- **WHEN** the user expands Calidad L1
- **THEN** the numbers are shown as a sample or unpublished
- **AND** they are not presented as an operator run

#### Scenario: Results document over HTTP
- **GIVEN** a running serving process with a results document
- **WHEN** a client requests `GET /evals/l1`
- **THEN** the response is HTTP 200 with the stored JSON object
- **AND** it contains `retrieval`, `generation`, `judge`, and `n`

#### Scenario: Missing document over HTTP
- **GIVEN** a running serving process whose evals directory has no `l1.json`
- **WHEN** a client requests `GET /evals/l1`
- **THEN** the response is HTTP 200
- **AND** `unpublished` and `sample` are true

#### Scenario: Weekday refresh skips L1
- **GIVEN** a scheduled refresh
- **WHEN** it completes without an opt-in flag
- **THEN** L1 is not executed

#### Scenario: Collector auth failure still writes L1
- **GIVEN** a collector endpoint is configured
- **AND** the collector rejects annotations as unauthenticated
- **WHEN** an operator L1 run finishes scoring
- **THEN** the static results document still contains the scores

### Requirement: Host install preserves operator L1
Installing or updating application code on the dump host MUST NOT replace an existing L1 results document on that host, whatever its flags. When no results document exists on that host, the install SHALL seed the results document committed at `evals/l1.json` in the deployed revision, read from version control, and MUST NOT seed an uncommitted working-tree document from the operator machine.

#### Scenario: Second install keeps operator numbers
- **GIVEN** an operator L1 run has replaced the results document on the dump host
- **WHEN** the operator updates application code on that host
- **THEN** the stored operator results remain

#### Scenario: First install may seed sample
- **GIVEN** the dump host has no L1 results document
- **AND** the committed `evals/l1.json` is labeled unpublished or sample
- **WHEN** the operator installs the application
- **THEN** that committed sample is present on the host
- **AND** it is labeled unpublished or sample

#### Scenario: First install seeds the committed document
- **GIVEN** the dump host has no L1 results document
- **AND** the committed `evals/l1.json` is a published operator run on the published dump
- **WHEN** the operator installs the application
- **THEN** the host serves that committed document
- **AND** a later operator run on the host replaces it

#### Scenario: First install does not seed a published laptop run
- **GIVEN** the dump host has no L1 results document
- **AND** the operator machine's working tree holds an uncommitted published L1 run that differs from the committed `evals/l1.json`
- **WHEN** the operator installs the application
- **THEN** the host receives the committed document, not the working-tree run
