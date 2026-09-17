## MODIFIED Requirements

### Requirement: Automated tests with fakes
The project SHALL provide a test command that runs unit and acceptance tests with fakes (no live LLM key required for L1) and SHALL emit a coverage report for the deterministic core. That default command MUST NOT require a running serving process, live mail, a browser, or a language-model key. The default command MUST NOT read the repository `.env` file into the process environment; settings defaults asserted by unit tests SHALL hold regardless of test order and regardless of the developer's `.env` contents. Live acceptance against the local serving process SHALL be a separate operator command and MUST NOT run as part of the default command. The live BCRA catalog download command MUST NOT execute live acceptance.

#### Scenario: Default test command
- **GIVEN** the repository test command
- **WHEN** it runs
- **THEN** unit and Gherkin suites execute with fakes
- **AND** a coverage report file is produced
- **AND** live mail, a browser, and a running serving process are not required

#### Scenario: Developer .env does not change unit-test outcomes
- **GIVEN** a repository `.env` that sets `MATOMO_URL`, `DEFAULT_K`, and `LLM_ENABLE_THINKING`
- **AND** the default test command runs the live/prod helper unit tests before the settings tests
- **WHEN** the settings defaults test constructs `Settings(_env_file=None)`
- **THEN** `matomo_url` is empty, `default_k` is 5, and `llm_enable_thinking` is true

#### Scenario: Live acceptance is not the default
- **GIVEN** the repository default test command
- **WHEN** it runs
- **THEN** live acceptance scenarios against the local serving process do not execute

#### Scenario: Catalog download does not run live acceptance
- **GIVEN** the live BCRA catalog download command
- **WHEN** it runs
- **THEN** live acceptance scenarios against the local serving process do not execute

## ADDED Requirements

### Requirement: Packaged static assets exist
Every static asset the wheel build force-includes MUST exist in the source tree, and the assets the serving process routes (`favicon.ico`, `favicon.svg`, `apple-touch-icon.png`, `og.png`, `weblab.css`, `observatory.css`, `guardrails/policy.yaml`) SHALL be included. The editable install (`uv sync`) MUST succeed on a clean checkout.

#### Scenario: Editable install builds
- **GIVEN** a clean checkout
- **WHEN** the operator runs `uv sync`
- **THEN** the build succeeds and no forced include is missing

#### Scenario: Include list is checked by a unit test
- **GIVEN** the wheel force-include table in `pyproject.toml`
- **WHEN** the default test command runs
- **THEN** a test asserts each listed source path is an existing file
