# evals-l1 Specification

## Purpose

Measure retrieval and citation quality offline against a labeled gold set so a screen can defend numbers, without running those evals in the browser or on every refresh.

## Requirements

### Requirement: Gold set
The system SHALL ship a Spanish-first gold file of 30–50 questions (MAY cap at 30 if labeling time runs out) labeled as an FX/compliance analyst. Rows MUST include id, question, gold comunicación ids, gold puntos when applicable, finding, and whether the question is answerable. Buckets MUST include definición, obligación/acceso, procedimiento/punto, silencio, cross-ref trap, superseded-trap, a post-TO patch (tipo de cambio de referencia A 3500 vs A 8359), and a few overlapping English questions that still cite Spanish puntos.

#### Scenario: Gold size
- **GIVEN** the shipped gold file
- **WHEN** an operator counts rows
- **THEN** there are between 30 and 50 questions inclusive, or exactly 30 if the cap was used

#### Scenario: Invented Com. is gold silencio
- **GIVEN** a gold row for Comunicación A 9999
- **WHEN** L1 is scored
- **THEN** gold finding is silencio
- **AND** gold citations are empty

#### Scenario: English question still cites Spanish punto
- **GIVEN** an English gold question about a TO clause
- **WHEN** L1 is scored
- **THEN** gold puntos still name the Spanish numbered clause

### Requirement: Published metrics
An L1 run SHALL publish at least: hit@5, MRR, citation-id exact match, RAGAS faithfulness and answer relevancy on the gold rows that have a written reference answer (8–12 rows), chunking A versus B on the structured slice, and a slice table (definición, obligación, silencio, cross-ref, superseded, post-TO patch). Citation-id exact SHALL be the headline metric.

#### Scenario: Published results exist after L1
- **GIVEN** an L1 run has completed
- **WHEN** an operator reads the published results
- **THEN** citation-id exact is presented as the headline number
- **AND** hit@5 and A vs B appear with the slice table
- **AND** the text states which documents strategy B covered

### Requirement: Static results file
L1 SHALL write a static results document that the assistant UI reads. The browser MUST NOT compute L1 scores. Refresh MUST NOT run L1 unless the operator opts in. A shipped placeholder results document MAY exist so the UI is not empty. The UI MUST label those numbers as unpublished or sample until an operator L1 run has replaced them.

#### Scenario: UI reads last run
- **GIVEN** a results file from the last L1 run
- **WHEN** the user opens Calidad L1
- **THEN** those stored numbers are shown
- **AND** no eval model is invoked in the client

#### Scenario: Shipped placeholder is labeled
- **GIVEN** only the shipped unpublished results document exists
- **WHEN** the user expands Calidad L1
- **THEN** the numbers are shown as a sample or unpublished
- **AND** they are not presented as an operator run

#### Scenario: Weekday refresh skips L1
- **GIVEN** a scheduled refresh
- **WHEN** it completes without an opt-in flag
- **THEN** L1 is not executed

### Requirement: CI does not pay for L1
Automated tests on every change MUST NOT call a paid language model for L1. Unit and acceptance tests use fakes. The default test command MUST NOT require RAGAS.

#### Scenario: Default test run
- **GIVEN** the project test command
- **WHEN** it runs in CI
- **THEN** it does not require a live LLM API key for L1
- **AND** it does not require RAGAS
