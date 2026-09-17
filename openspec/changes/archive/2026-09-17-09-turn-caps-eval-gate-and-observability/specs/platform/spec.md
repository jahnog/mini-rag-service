## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Per-turn judge runs after the response
When per-turn evaluation is enabled, the serving process SHALL return the chat response as soon as the answer is final and SHALL score faithfulness and answer relevancy in a background task. The `chat.turn` trace span SHALL stay open until scoring ends so the scores attach to that span, and the `chat_turn_eval` log line SHALL still be written. A scoring failure MUST NOT affect the already-returned response. Turns that did not call the language model SHALL NOT be scored.

#### Scenario: Response does not wait for the judge
- **GIVEN** per-turn evaluation is enabled with a judge that takes 2 seconds
- **WHEN** an in-corpus question is answered
- **THEN** the response returns before the judge finishes
- **AND** after the judge finishes the `chat.turn` span carries `eval.faithfulness` and `eval.answer_relevancy`
