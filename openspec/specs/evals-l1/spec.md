# evals-l1 Specification

## Purpose

Measure retrieval and citation quality offline against a labeled gold set so a screen can defend numbers, without running those evals in the browser or on every refresh.

## Requirements

### Requirement: Gold set
The system SHALL ship a Spanish-first gold file of 30–50 questions (MAY cap at 30 if labeling time runs out) labeled as an FX/compliance analyst. Rows MUST include id, question, gold comunicación ids, gold puntos when applicable, finding, and whether the question is answerable. Between 8 and 12 answerable rows MUST include a written Spanish reference answer in the cited-clause shape (including `Fuente:` when citations exist) that names the same gold ids and puntos. Those reference rows SHOULD also have gold puntos so oracle context is a numbered clause. Silencio rows MUST NOT include a reference answer. Buckets MUST include definición, obligación/acceso, procedimiento/punto, silencio, cross-ref trap, superseded-trap, a post-TO patch (tipo de cambio de referencia A 3500 vs A 8359), and a few overlapping English questions that still cite Spanish puntos.

#### Scenario: Gold size
- **GIVEN** the shipped gold file
- **WHEN** an operator counts rows
- **THEN** there are between 30 and 50 questions inclusive, or exactly 30 if the cap was used

#### Scenario: Invented Com. is gold silencio
- **GIVEN** a gold row for Comunicación A 9999
- **WHEN** L1 is scored
- **THEN** gold finding is silencio
- **AND** gold citations are empty
- **AND** the row has no reference answer

#### Scenario: English question still cites Spanish punto
- **GIVEN** an English gold question about a TO clause
- **WHEN** L1 is scored
- **THEN** gold puntos still name the Spanish numbered clause

#### Scenario: Reference rows have puntos
- **GIVEN** the 8–12 gold rows that carry a written reference answer
- **WHEN** an operator inspects those rows
- **THEN** each row whose gold ids include texto_ordenado has gold puntos
- **AND** Comunicación A-only reference rows MAY omit puntos
- **AND** the reference answer names the same gold ids

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

### Requirement: Independent retrieval and generation suites
An L1 run SHALL evaluate retrieval and generation independently. Retrieval metrics MUST NOT require a generated answer and MUST NOT call the chat language model. Generation metrics MUST score against an explicit stuffed context and MUST NOT search the index. The published results MUST contain two separate blocks (`retrieval` and `generation`) and MUST NOT publish a blended overall RAG score. Suites that did not run MUST be marked skipped with a reason and MUST NOT be filled with zeros as if they scored.

#### Scenario: Retrieval-only run does not generate
- **GIVEN** an operator L1 run limited to retrieval
- **WHEN** the run completes
- **THEN** the retrieval block is present with scores
- **AND** the generation block is skipped with a reason
- **AND** the chat language model was not called

#### Scenario: Generation-only run does not search
- **GIVEN** an operator L1 run limited to generation with oracle context
- **WHEN** the run completes
- **THEN** the generation block is present with scores
- **AND** the retrieval block is skipped with a reason
- **AND** the index was not searched for those gold questions

#### Scenario: Silencio gold does not zero judged generation
- **GIVEN** a gold row for Comunicación A 9999 with empty gold citations and finding silencio
- **WHEN** generation is scored
- **THEN** finding exact and citation-id exact are scored
- **AND** faithfulness and answer relevancy are skipped for that row
- **AND** those skipped judged metrics are not treated as 0

#### Scenario: Named Com. A uses oracle clause not live search
- **GIVEN** a gold row whose gold ids include Comunicación A 3500
- **AND** generation context is oracle
- **WHEN** generation is scored
- **THEN** the stuffed context is that comunicación’s dump text
- **AND** the index search path is not used

#### Scenario: Vigente gold still has a retrieval score
- **GIVEN** a gold row that asks what is required today to liquidate
- **WHEN** retrieval is scored
- **THEN** hit@5 and precision@5 are computed against the gold dump ids
- **AND** no generated answer is required

### Requirement: Oracle generation context
Default generation context SHALL be oracle gold dump text: for each gold id, the dump section for that id, using gold puntos when present (puntos apply to the texto ordenado; Comunicaciones A use the document extract). Concatenated oracle context MUST NOT exceed the configured maximum context size. When a row has gold ids but no punto and no usable clause, judged faithfulness and answer relevancy for that row MUST be skipped. Generation with retrieved context MAY be selected by the operator and MUST use hits already produced by a retrieval suite in the same run, not a second search.

#### Scenario: Oracle uses TO punto
- **GIVEN** a gold row with gold id texto_ordenado and gold punto 3.8.5
- **AND** generation context is oracle
- **WHEN** generation is scored
- **THEN** the stuffed context is the texto ordenado clause for punto 3.8.5
- **AND** the index is not searched

#### Scenario: Oracle Comunicación A has no punto
- **GIVEN** a gold row whose gold ids include Comunicación A 8359 and no gold punto
- **AND** generation context is oracle
- **WHEN** generation is scored
- **THEN** the stuffed context is that comunicación’s dump extract

#### Scenario: Retrieved context is passed in
- **GIVEN** retrieval has already produced hits for a gold question in the same run
- **AND** the operator selected retrieved generation context
- **WHEN** generation is scored
- **THEN** those hits are the stuffed context
- **AND** generation does not search again

### Requirement: Judged metrics may be skipped
Faithfulness, answer relevancy, context precision, and context recall SHALL be computed by a judge language model when the operator environment provides a judge key and the optional eval extra. When that extra or key is missing, those judged values MUST be omitted with a skip reason. Code metrics (hit@5, precision@5, MRR, citation-id exact, citation-punto exact, citation-snippet grounded, finding exact, latencies) MUST still publish. Context recall MUST run only on gold rows that have a written reference answer. The default automated test command MUST NOT require the judge extra.

#### Scenario: Dry run without a judge still publishes code metrics
- **GIVEN** no judge key and no eval extra
- **WHEN** an operator L1 run completes
- **THEN** hit@5, precision@5, MRR, citation-id exact, and finding exact are present
- **AND** judged metrics are skipped with a reason
- **AND** they are not shown as 0

#### Scenario: Context recall skips silencio
- **GIVEN** a gold row with no reference answer
- **WHEN** retrieval judged metrics run
- **THEN** context recall is skipped for that row
- **AND** is not treated as 0

### Requirement: Static results file
L1 SHALL write a static results document that the assistant UI reads. The browser MUST NOT compute L1 scores. Refresh MUST NOT run L1 unless the operator opts in. The repository SHALL commit a results document at `evals/l1.json`. That document MAY be a published operator run made on the published dump (the dump that `scripts/publish-data.sh` ships), in which case it carries `unpublished: false` and `sample: false`; otherwise it MUST be labeled unpublished or sample. The UI SHALL label the numbers strictly by those flags. The document MUST mark judged metrics skipped, not zero, when the judge did not run. A collector error, including an authentication failure, MUST NOT fail that static write. The serving process SHALL expose the stored document read-only at `GET /l1`; when no document exists it SHALL return the same unpublished stub the UI renders, with HTTP 200.

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
- **WHEN** a client requests `GET /l1`
- **THEN** the response is HTTP 200 with the stored JSON object
- **AND** it contains `retrieval`, `generation`, `judge`, and `n`

#### Scenario: Missing document over HTTP
- **GIVEN** a running serving process whose evals directory has no `l1.json`
- **WHEN** a client requests `GET /l1`
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

### Requirement: Dump-host published run
An operator L1 run on the host that stores the dump SHALL score against that dump’s index when the index is ready. Published staff L1 numbers (Calidad L1 without the unpublished/sample banner) MUST come from an operator run on that dump whose index was ready. A run on a machine whose index is not ready MUST still be labeled unpublished or sample and MUST NOT be presented as dump quality. A shipped unpublished sample MAY still be shown until a published run exists. Citation-id exact SHALL remain the headline metric.

#### Scenario: Dump-host run is published
- **GIVEN** the dump index is ready on the host
- **WHEN** an operator L1 run completes on that host
- **THEN** the static results document is not labeled unpublished or sample
- **AND** citation-id exact is presented as the headline number

#### Scenario: Run without a ready index stays sample
- **GIVEN** no dump has been ingested on the machine that runs L1
- **WHEN** an operator L1 run completes
- **THEN** the results are labeled unpublished or sample
- **AND** they are not presented as dump quality

#### Scenario: Invented Com. still scores silencio on the dump host
- **GIVEN** a gold row for Comunicación A 9999
- **AND** the dump index is ready
- **WHEN** L1 is scored on the dump host
- **THEN** gold finding is silencio
- **AND** gold citations are empty

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

### Requirement: CI does not pay for L1
Automated tests on every change MUST NOT call a paid language model for L1. Unit and acceptance tests use fakes. The default test command MUST NOT require RAGAS and MUST NOT require a live collector or a judge extra.

#### Scenario: Default test run
- **GIVEN** the project test command
- **WHEN** it runs in CI
- **THEN** it does not require a live LLM API key for L1
- **AND** it does not require RAGAS
- **AND** it does not require a live collector

### Requirement: Threshold gate
The L1 command SHALL accept a gate option that reads per-metric floors from a TOML file (`evals/gate.toml` by default, `[thresholds]` table of metric name to minimum value). After the run it SHALL compare each listed metric from the published retrieval or generation block against its floor, print one line per failing metric naming the value and the floor, and exit non-zero when any metric fails. A suite that was skipped SHALL fail the gate for its metrics unless the operator allows skipped suites. The default test command MUST NOT run the gate.

#### Scenario: All metrics at or above floors
- **GIVEN** floors `hit_at_5 = 0.8` and `citation_id_exact = 0.2`
- **AND** the run publishes hit@5 0.87 and citation-id exact 0.23
- **WHEN** the operator runs L1 with the gate
- **THEN** the command prints `GATE OK` and exits 0

#### Scenario: A metric under its floor
- **GIVEN** floor `mrr = 0.7`
- **AND** the run publishes MRR 0.65
- **WHEN** the operator runs L1 with the gate
- **THEN** the command prints a line containing `mrr: 0.65 < 0.7`
- **AND** exits non-zero

#### Scenario: Skipped generation fails unless allowed
- **GIVEN** floors for `finding_exact`
- **AND** the generation suite was skipped
- **WHEN** the operator runs L1 with the gate and without allowing skipped suites
- **THEN** the command exits non-zero naming the skipped suite
- **WHEN** the operator allows skipped suites
- **THEN** that metric is not a failure
