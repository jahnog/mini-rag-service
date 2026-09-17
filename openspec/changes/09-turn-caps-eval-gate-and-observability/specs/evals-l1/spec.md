## ADDED Requirements

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
