# platform Specification

## Purpose

Keep the service operable when the dump is empty, honest about dates, cheap enough to demo, and checked by automated tests without paying for L1 on every change.

## Requirements

### Requirement: Health document
The system SHALL expose `GET /health` that reports last_refresh, to_as_of, last_comm_id, n_docs, and index_ready. It SHOULD also report the embedding model name. When the dump or index is missing, the process SHALL still start and health SHALL return `index_ready` false with HTTP 200. last_refresh, to_as_of, and last_comm_id SHALL still be present (null is allowed). n_docs SHALL still be present (0 is allowed). The system MUST NOT use HTTP 503 solely because the index is empty.

#### Scenario: Empty dump
- **GIVEN** no dump has been ingested
- **WHEN** the service starts
- **THEN** GET /health succeeds with HTTP 200
- **AND** index_ready is false
- **AND** last_refresh, to_as_of, last_comm_id, and n_docs are present

### Requirement: Disclaimer
Every answer and the interface footer SHALL state that the extract is unofficial, not BCRA, not legal advice, and dated as of last_refresh.

#### Scenario: Disclaimer on silencio
- **GIVEN** any chat response
- **WHEN** it is shown
- **THEN** the unofficial-extract wording and last_refresh appear

### Requirement: Message size and k caps
The system SHALL reject a message longer than the configured maximum (default 4000 characters) and SHALL cap retrieval k at the configured maximum (default 8). Oversized messages MUST NOT retrieve, MUST NOT call the language model, and MUST NOT produce invented CAMEX text.

#### Scenario: Oversized message
- **GIVEN** a message longer than the configured maximum
- **WHEN** it is posted
- **THEN** the system rejects it without producing CAMEX clauses
- **AND** the language model is not called

### Requirement: Rate limit
The system SHALL apply a crude per-client rate limit (default 20 chat requests per 60 seconds) and SHALL queue concurrent UI users. Extra requests SHALL be rejected or delayed and MUST NOT each produce a full CAMEX answer. An optional shared demo secret MAY be required when the UI is on a public URL. A local demo MAY leave that secret unset. Client identity for this limit SHALL use the same trusted-proxy rule as authentication (connecting address unless trusted-proxy is on). Unauthenticated requests MUST NOT consume this chat budget (they fail authentication first).

#### Scenario: Repeated requests are limited
- **GIVEN** an authenticated client that exceeds the configured request rate
- **WHEN** further chat requests are sent
- **THEN** those extra requests are rejected or delayed
- **AND** they do not each produce a full CAMEX answer

#### Scenario: Unauthenticated 401 does not eat the chat budget
- **GIVEN** no session credential
- **AND** the chat rate limit is 2 requests per 60 seconds
- **WHEN** three unauthenticated chat requests are sent
- **THEN** each is HTTP 401
- **AND** a later authenticated request is not rejected solely because of those three

### Requirement: Unauthenticated chat is rejected
`POST /chat` and `POST /chat/clear` SHALL require a valid session. Without one they SHALL return HTTP 401, MUST NOT retrieve, MUST NOT call the language model, MUST NOT write chat session memory, and MUST NOT produce invented CAMEX text. An optional shared demo secret, when configured, SHALL still be required in addition to the session (not instead of it). The existing per-client chat rate limit SHALL apply only after the session is accepted.

#### Scenario: Repeated unauthenticated posts do not call the model
- **GIVEN** no session credential
- **WHEN** several chat requests are sent
- **THEN** each response is HTTP 401
- **AND** the language model is not called

#### Scenario: Demo secret is not a substitute for the session
- **GIVEN** a configured demo secret
- **AND** no session credential
- **WHEN** a chat request is sent with that demo secret
- **THEN** the response is HTTP 401
- **AND** the language model is not called

### Requirement: Single-process session memory
Chat session memory is in-process. The serving process SHALL run as one worker. v1 MUST NOT serve chat from multiple replicas that do not share that memory.

#### Scenario: Two sessions on one process
- **GIVEN** the chat process is running
- **WHEN** two clients use different session ids at the same time
- **THEN** each session keeps its own last turns
- **AND** one session’s `/clear` does not wipe the other

### Requirement: Chat memory is bound to the authenticated email
Chat turn memory SHALL belong to the authenticated email. The public session id on the wire SHALL remain a UUID. A later authenticated client that presents the same session id under a different email MUST NOT retrieve, continue, or send those prior turns to the language model. The same email with the same session id SHALL still resume. Unauthenticated requests still MUST NOT write chat session memory.

#### Scenario: Follow-up does not leak across mailboxes
- **GIVEN** an authenticated session for `ops@example.com` with a prior turn
- **AND** that turn’s session id
- **WHEN** `other@example.com` is authenticated and posts a follow-up with that session id
- **THEN** the language model is not given the prior turn from `ops@example.com`
- **AND** the response is not HTTP 401

#### Scenario: Same mailbox still follows up
- **GIVEN** an authenticated session for `ops@example.com` with a prior turn
- **WHEN** that mailbox posts a follow-up with the same session id
- **THEN** the language model receives that prior turn

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

### Requirement: Shared dump for refresh and chat
Refresh, chat, and operator L1 on the dump host SHALL read the same dump and index on the host that stores them.

#### Scenario: Same dump for API and refresh
- **GIVEN** ingest wrote documents on the host dump
- **WHEN** the API answers a question
- **THEN** it reads that same dump and index

#### Scenario: Same dump for dump-host L1
- **GIVEN** ingest wrote documents on the host dump
- **AND** the index is ready
- **WHEN** the operator runs L1 on that host
- **THEN** L1 reads that same dump and index

### Requirement: Operator dump-host L1
An operator MAY run L1 on the dump host against the same dump and index that chat uses. That command MUST accept the same suite choices as the laptop operator command (retrieval only, generation only, both, and skip the judge). It MUST NOT start the assistant interface.

#### Scenario: Dump-host L1 uses the host dump
- **GIVEN** ingest wrote documents on the host dump
- **AND** the index is ready
- **WHEN** the operator runs L1 on that host
- **THEN** scoring uses that same dump and index
- **AND** the static results document is written

### Requirement: Dump-host L1 serializes with host jobs
Dump-host L1 MUST serialize with ingest and refresh so those jobs do not run at the same time as L1.

#### Scenario: Dump-host L1 does not overlap refresh
- **GIVEN** a scheduled refresh is running
- **WHEN** the operator starts dump-host L1
- **THEN** L1 waits until refresh finishes
- **OR** refresh waits until L1 finishes

#### Scenario: Dump-host L1 does not overlap ingest
- **GIVEN** ingest is running
- **WHEN** the operator starts dump-host L1
- **THEN** L1 waits until ingest finishes
- **OR** ingest waits until L1 finishes

### Requirement: Dump-host L1 stops and reloads serving
Dump-host L1 MUST stop the serving process for the duration of the run. In-process chat sessions MUST NOT survive that stop. After the run finishes or fails, the serving process MUST be running again. After a dump-host operator run, staff Calidad L1 SHALL read the reloaded static document.

#### Scenario: Named Com. A still answers after L1 reload
- **GIVEN** the dump contains Comunicación A 3500
- **AND** a dump-host L1 run has finished and the serving process has reloaded
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** a structured chat response is still returned

#### Scenario: Clear still works after L1 reload
- **GIVEN** a dump-host L1 run has finished and the serving process has reloaded
- **WHEN** the user clicks Clear
- **THEN** Clear is still available
- **AND** the next question does not use turns from before the reload

#### Scenario: Serving is up if L1 fails
- **GIVEN** dump-host L1 has failed
- **WHEN** the operator inspects the host
- **THEN** the serving process is running

### Requirement: Optional trace collector
The serving process MAY export per-turn traces to a collector endpoint when that endpoint is configured. When the endpoint is set, the process MAY also send a configured API key with those exports. An unset key SHALL still export to an unauthenticated collector. Export MUST fail open: a collector error, including an authentication failure, MUST NOT fail chat. When the endpoint is unset, the process SHALL still answer. When the endpoint is set, retrieval steps MAY be exported as retriever spans that include retrieved document identifiers and truncated document text. Default automated tests MUST NOT require a live collector or a real collector key. Hostnames MUST NOT be hardcoded; the collector URL is configuration.

#### Scenario: Unset collector still answers
- **GIVEN** no collector endpoint is configured
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned

#### Scenario: Retriever spans on chat
- **GIVEN** a collector endpoint is configured
- **WHEN** the user asks what is required today to liquidate
- **THEN** a retriever span MAY be exported for that turn
- **AND** chat still returns a structured response if export fails

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

### Requirement: Local traces alongside optional collector
The serving process MAY export per-turn traces to a collector endpoint when that endpoint is configured. Export MUST fail open: a collector error MUST NOT fail chat. Whether or not that endpoint is set, the process SHALL also write compact per-span records to a dump-host traces file. A failure to write that file MUST NOT fail chat. Default automated tests MUST NOT require a live collector.

#### Scenario: Unset collector still answers and still writes local traces
- **GIVEN** no collector endpoint is configured
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned
- **AND** the dump-host traces file includes a `chat.turn` record

#### Scenario: Collector error still answers
- **GIVEN** a collector endpoint is configured
- **AND** export to that collector fails
- **WHEN** the user asks an in-corpus question
- **THEN** a structured chat response is still returned
- **AND** the dump-host traces file still includes a `chat.turn` record

### Requirement: Language-model timeout
The system SHALL bound a language-model call with a configured timeout (default 60 seconds). That bound SHALL be wall-clock for the whole call, including while a streaming thinking trace is still arriving and including any retry. On timeout the turn SHALL be silencio with abstain reason `llm_timeout`, citations SHALL be empty, the answer SHALL be a Spanish sentence saying the model took too long, and the serving process SHALL still return a structured chat response. The system MUST NOT invent CAMEX text from a partial stream.

#### Scenario: Timed-out generation is silencio
- **GIVEN** the language-model call exceeds the configured timeout
- **WHEN** the request is processed
- **THEN** finding is silencio
- **AND** `abstain_reason` is `llm_timeout`
- **AND** citations are empty

#### Scenario: Thinking tokens past the bound still silencio
- **GIVEN** the language-model provider keeps sending thinking tokens past the configured timeout
- **WHEN** the request is processed
- **THEN** finding is silencio
- **AND** citations are empty
- **AND** the serving process still returns a structured chat response

### Requirement: Daily language-model turn caps
The system SHALL count an authenticated chat question that passes the session check, the demo-secret check when that secret is configured, and the per-client burst rate limit toward daily caps; the burst limit SHALL be checked before the daily caps so a burst-refused request does not count. Chat-clear MUST NOT count. Unauthenticated requests MUST NOT count. After 30 counted turns in the current UTC day for that normalized email, or 100 counted turns in the current UTC day for the serving process, whichever happens first, a further counted question SHALL be HTTP 429, MUST NOT call the language model, and MUST NOT produce CAMEX clauses. A refused cap turn MUST NOT itself increment either cap. A counted question that an enforced input guardrail blocks (length, secrets, no-advice, injection, scope) SHALL be refunded to both caps once the turn completes, and the process SHALL log the refund with the same hashed email prefix. The process SHALL log that the email cap or the process cap was reached without persisting the full email, the session credential, or message text. Plus-tags SHALL share the email cap of the collapsed mailbox.

#### Scenario: Thirty-first turn for one mailbox is refused
- **GIVEN** an authenticated session for `ops@example.com`
- **AND** that mailbox has already completed 30 language-model turns today
- **WHEN** that client posts another CAMEX question
- **THEN** the response is HTTP 429
- **AND** the language model is not called
- **AND** the process log records that the email cap was reached
- **AND** the full email is not in that log

#### Scenario: Process cap can fire first
- **GIVEN** two authenticated mailboxes that have together completed 100 language-model turns today
- **AND** neither mailbox is at 30 turns
- **WHEN** either client posts another CAMEX question
- **THEN** the response is HTTP 429
- **AND** the language model is not called
- **AND** the process log records that the process cap was reached

#### Scenario: Blocked question is refunded
- **GIVEN** an authenticated session whose email cap is 2 turns per day
- **WHEN** the client asks about the weather in Madrid twice and then asks a CAMEX question
- **THEN** the two weather turns are scope-blocked
- **AND** the CAMEX question is answered, not HTTP 429

#### Scenario: Burst-limited request does not count
- **GIVEN** an authenticated session whose email cap is 1 turn per day
- **AND** the per-client burst limit is already exhausted
- **WHEN** the client posts a CAMEX question
- **THEN** the response is HTTP 429
- **AND** a later request after the burst window is not refused because of the email cap

#### Scenario: Clear does not consume the email cap
- **GIVEN** an authenticated session that has already completed 30 language-model turns today
- **WHEN** the client posts chat-clear
- **THEN** the language model is not called
- **AND** the response is not HTTP 429 solely because of the email cap

#### Scenario: Unauthenticated 401 does not consume caps
- **GIVEN** no session credential
- **AND** the email cap is 2 language-model turns per day
- **WHEN** three unauthenticated chat requests are sent
- **THEN** each is HTTP 401
- **AND** a later authenticated request is not refused solely because of those three

#### Scenario: Plus-tag shares the email cap
- **GIVEN** an authenticated session for `ops+staff@example.com`
- **AND** `ops@example.com` has already completed 30 language-model turns today
- **WHEN** that client posts a CAMEX question
- **THEN** the response is HTTP 429
- **AND** the language model is not called

#### Scenario: Named Com. A still answers under the cap
- **GIVEN** an authenticated session with fewer than 30 language-model turns today
- **AND** the process is under 100 language-model turns today
- **AND** Comunicación A 3500 is in the dump
- **WHEN** the client asks what Comunicación A 3500 says
- **THEN** a citation id is `A3500`

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

### Requirement: Language-model generation settings
The system SHALL expose generation controls as settings: `LLM_TEMPERATURE` (default 0.1, 0–2), `LLM_MAX_TOKENS` (default 1500, at least 64), `LLM_SEED` (unset by default), `LLM_REASONING_BUDGET` (default 0 meaning provider default; sent to the provider only when greater than 0 and never to x.ai hosts) and `LLM_THINKING_USER_LAYOUT` (default false). Every language-model call SHALL send temperature and max tokens; it SHALL send the seed only when set. A call MAY override the thinking flag per turn; when no override is given the `LLM_ENABLE_THINKING` setting applies.

#### Scenario: Defaults reach the provider
- **GIVEN** default settings against a local provider
- **WHEN** a turn calls the language model
- **THEN** the request carries temperature 0.1 and max tokens 1500
- **AND** it carries no seed and no reasoning budget

#### Scenario: Budget and seed when configured
- **GIVEN** `LLM_SEED=7` and `LLM_REASONING_BUDGET=512` against a local provider
- **WHEN** a turn calls the language model
- **THEN** the request carries seed 7
- **AND** the provider extra body carries reasoning budget 512

#### Scenario: Per-call thinking override wins
- **GIVEN** `LLM_ENABLE_THINKING=true`
- **WHEN** a call is made with thinking overridden to off
- **THEN** the provider extra body has thinking disabled for that call only

### Requirement: Retrieval and health run off the event loop
The serving process SHALL execute the dump-health check and the routing/retrieval step of a chat turn in a worker thread, so a second concurrent turn is not blocked by the first turn's embedding call or index query. The dump manifest SHALL be parsed once per file version (path, modification time, size) and the health document cached per manifest version; a rewritten manifest SHALL be picked up on the next turn without a restart.

#### Scenario: Concurrent turns do not serialize on retrieval
- **GIVEN** an index whose search takes 300 ms
- **WHEN** two chat turns start at the same time
- **THEN** both complete in about 300 ms of retrieval wall time, not 600 ms

#### Scenario: Rewritten manifest refreshes health
- **GIVEN** a cached health document for the current manifest
- **WHEN** the manifest file is rewritten with a new `last_refresh`
- **THEN** the next health document reports the new `last_refresh`

### Requirement: Per-turn judge runs after the response
When per-turn evaluation is enabled, the serving process SHALL return the chat response as soon as the answer is final and SHALL score faithfulness and answer relevancy in a background task. The `chat.turn` trace span SHALL stay open until scoring ends so the scores attach to that span, and the `chat_turn_eval` log line SHALL still be written. A scoring failure MUST NOT affect the already-returned response. Turns that did not call the language model SHALL NOT be scored.

#### Scenario: Response does not wait for the judge
- **GIVEN** per-turn evaluation is enabled with a judge that takes 2 seconds
- **WHEN** an in-corpus question is answered
- **THEN** the response returns before the judge finishes
- **AND** after the judge finishes the `chat.turn` span carries `eval.faithfulness` and `eval.answer_relevancy`
