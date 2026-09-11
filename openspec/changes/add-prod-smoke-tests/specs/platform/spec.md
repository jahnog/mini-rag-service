## ADDED Requirements

### Requirement: Production smoke is a separate operator command
The project SHALL provide a production-smoke command, separate from the default test command and from live local-acceptance, that exercises the already-running serving process at a configured public origin. That command MUST NOT run as part of the default test command or the default CI workflow. The live local-acceptance command and the live BCRA catalog download command MUST NOT execute production smoke. This requirement does not change the existing fakes-only default test command.

#### Scenario: Production smoke is not the default
- **GIVEN** the repository default test command
- **WHEN** it runs
- **THEN** production smoke scenarios against the public origin do not execute

#### Scenario: Default CI does not run production smoke
- **GIVEN** the default CI workflow
- **WHEN** it runs
- **THEN** production smoke scenarios do not execute

#### Scenario: Catalog download does not run production smoke
- **GIVEN** the live BCRA catalog download command
- **WHEN** it runs
- **THEN** production smoke scenarios against the public origin do not execute

#### Scenario: Live acceptance does not run production smoke
- **GIVEN** the live local-acceptance command
- **WHEN** it runs
- **THEN** production smoke scenarios against the public origin do not execute
