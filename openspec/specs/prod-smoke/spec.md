# prod-smoke Specification

## Purpose

Exercise the already-running public origin over HTTP on operator demand.

## Requirements

### Requirement: Production smoke is opt-in against a running process
The project SHALL provide a production-smoke command, separate from the default test command, that exercises the already-running serving process at a configured public origin over the network. That command MUST NOT start the serving process. When the operator has not invoked the production-smoke command, those scenarios MUST NOT run. When the operator has invoked it and the serving process is not reachable, the request origin does not match the public origin or mail retrieval is not configured, the command SHALL fail (not skip). Live local-acceptance tests and live BCRA catalog download tests remain different commands. The production-smoke command MUST NOT execute those other suites, and those other suites MUST NOT execute production smoke.

#### Scenario: Default tests stay fake
- **GIVEN** the repository default test command
- **WHEN** it runs without the production-smoke command
- **THEN** production-smoke scenarios do not execute
- **AND** in-process Gherkin with fakes still runs

#### Scenario: Production-smoke command needs the process
- **GIVEN** the operator invoked the production-smoke command
- **AND** no serving process is reachable at the configured public origin
- **THEN** the command fails
- **AND** it does not start a serving process

#### Scenario: Mismatched origin fails
- **GIVEN** the operator invoked the production-smoke command
- **AND** the request origin does not match the configured public origin
- **THEN** the command fails before sending mail

#### Scenario: Production smoke does not run catalog downloads
- **GIVEN** the operator invoked the production-smoke command
- **WHEN** it runs
- **THEN** live BCRA catalog download tests do not execute

### Requirement: One-time secret travels through real mail
When the production-smoke suite requests a one-time secret for an allowlisted mailbox against the running process, the process SHALL send a new message through its configured mail transport. The suite SHALL read that secret from the mailbox. The body SHALL contain a 6-digit secret and, when a public origin is configured, a login URL under that origin whose path carries a login token. The subject SHALL NOT contain that secret or the token. The suite MUST NOT treat an unused leftover message as proof of a new send. The suite MUST NOT inject a fake mail adapter into the running process. The serving process MUST NOT implement mailbox retrieval.

#### Scenario: Allowlisted mailbox receives a 6-digit secret and a login URL
- **GIVEN** a running serving process with mail configured and a public origin
- **AND** an allowlist that includes the production-smoke mailbox
- **WHEN** a client requests a one-time secret for that mailbox
- **THEN** a new message is available from that mailbox
- **AND** the body contains a 6-digit secret
- **AND** the body contains a login URL under the public origin
- **AND** the subject does not contain that secret
- **AND** the subject does not contain the token

### Requirement: Typed secret authenticates
Submitting the allowlisted email and the 6-digit secret from that new message SHALL authenticate. Success SHALL set an HTTP-only session credential. A session probe SHALL report that email. When the public origin is HTTPS, the credential SHALL be marked Secure. The secret SHALL be single-use.

#### Scenario: Correct code authenticates
- **GIVEN** a 6-digit secret just read from a new message in the allowlisted mailbox
- **WHEN** the client submits that email and that secret
- **THEN** the session probe reports authenticated with that email
- **AND** the session credential is not readable from page script

#### Scenario: HTTPS origin sets a Secure credential
- **GIVEN** a valid unexpired secret
- **AND** the public origin is HTTPS
- **WHEN** the client verifies from that origin
- **THEN** the session credential is marked Secure
- **AND** it is not readable from page script

### Requirement: Login link authenticates
Opening the login URL from a new message SHALL NOT set a session on the token path. A client that did not request that secret SHALL confirm on a page that names the mailbox, then submit. Success SHALL authenticate that mailbox, set an HTTP-only session credential, and consume the 6-digit secret. Typed use of that secret afterwards MUST NOT authenticate.

#### Scenario: Confirm from the mail URL authenticates
- **GIVEN** a new message whose body contains a login URL for the allowlisted mailbox
- **AND** a client that did not request that secret
- **WHEN** that client opens the login URL and submits the confirm form from the public origin
- **THEN** the session probe reports authenticated with that mailbox
- **AND** the 6-digit secret from that message no longer authenticates

### Requirement: Named Com. A and out-of-scope weather
With a valid session, `POST /chat` SHALL return the structured contract: answer, finding, citations, guardrails, session id, `last_refresh`, and `to_as_of`. When health reports `index_ready` false, the production-smoke command SHALL fail (not skip). When the client asks what Comunicación A 3500 says, the suite SHALL fail if the finding is `silencio` (including `llm_unavailable` or `missing_document`) and SHALL require a citation id `A3500` when the finding is not `silencio`. When the client asks about the weather, the finding SHALL be `silencio` and the scope rule SHALL be `block`. Exact clause wording MUST NOT be required.

#### Scenario: Health is ready
- **GIVEN** no session credential
- **WHEN** the client requests health from the running process
- **THEN** the response is HTTP 200
- **AND** `index_ready`, `last_refresh`, `to_as_of`, `last_comm_id`, and `n_docs` are present
- **AND** `index_ready` is true

#### Scenario: Named Com. A when the index is ready
- **GIVEN** an authenticated session
- **AND** health reports `index_ready` true
- **WHEN** the client asks what Comunicación A 3500 says
- **THEN** a citation id is `A3500`

#### Scenario: Weather is out of scope
- **GIVEN** an authenticated session
- **WHEN** the client asks about the weather in Madrid
- **THEN** the finding is silencio
- **AND** the scope rule is block

### Requirement: Published L1 document is served
The production-smoke command SHALL request `GET /l1` from the running public process and SHALL fail (not skip) when the response is not HTTP 200, when it lacks `retrieval`, `generation`, or `n`, or when `unpublished` or `sample` is true. It MUST NOT run L1.

#### Scenario: Host serves a published run
- **GIVEN** the operator invoked the production-smoke command
- **WHEN** the client requests `GET /l1`
- **THEN** the response is HTTP 200
- **AND** `unpublished` and `sample` are false
- **AND** `retrieval`, `generation`, and `n` are present

#### Scenario: Host has only the stub
- **GIVEN** the public process has no results document
- **WHEN** the production-smoke command requests `GET /l1`
- **THEN** the command fails and names the missing published run
