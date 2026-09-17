## MODIFIED Requirements

### Requirement: Live acceptance is opt-in against a running process
The project SHALL provide a live acceptance command, separate from the default test command, that exercises the already-running local serving process over the network. That command MUST NOT start the serving process. When the operator has not invoked the live command, those scenarios MUST NOT run and the repository `.env` MUST NOT be read into the process environment. When the operator has invoked it, the command SHALL load the repository `.env` (without overriding variables already set) before resolving the base URL and mailbox settings; if the serving process is not reachable, or mail retrieval is not configured, the command SHALL fail (not skip). Browser observatory scenarios MAY be omitted from a live run that the operator limits to HTTP. Live BCRA catalog download tests remain a different command. The live acceptance command MUST NOT execute catalog download tests.

#### Scenario: Default tests stay fake
- **GIVEN** the repository default test command
- **WHEN** it runs without the live acceptance command
- **THEN** live server, mailbox, browser, and language-model scenarios do not execute
- **AND** the repository `.env` is not loaded into the environment
- **AND** in-process Gherkin with fakes still runs

#### Scenario: Live command loads .env first
- **GIVEN** the operator invoked the live acceptance command
- **AND** `.env` defines `LIVE_BASE_URL` and `LIVE_IMAP_HOST`
- **AND** `LIVE_BASE_URL` is also set in the shell
- **WHEN** the session starts
- **THEN** `LIVE_IMAP_HOST` comes from `.env`
- **AND** `LIVE_BASE_URL` keeps the shell value

#### Scenario: Live command needs the process
- **GIVEN** the operator invoked the live acceptance command
- **AND** no local serving process is reachable
- **THEN** the command fails
- **AND** it does not start a serving process

#### Scenario: Live command does not run catalog downloads
- **GIVEN** the operator invoked the live acceptance command
- **WHEN** it runs
- **THEN** live BCRA catalog download tests do not execute
