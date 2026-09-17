## MODIFIED Requirements

### Requirement: Staff payloads stay off the wire in Usuario
When the layout is the end-user layout, or the client is not authenticated, the assistant interface MUST NOT stream a thinking trace into the conversation and MUST NOT include a thinking region in the rendered turn. The citation inspector and the per-query guardrail log SHALL be computed for every turn regardless of layout, so that the hidden side inspector always describes the latest answer; the end-user layout only hides them. Authenticated staff layout keeps the existing thinking, inspector, and trust contracts.

#### Scenario: Usuario turn does not stream thinking
- **GIVEN** an authenticated session
- **AND** the interface is in the end-user layout
- **AND** the language-model provider would return a reasoning trace
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the conversation shows the cited answer
- **AND** the thinking region is not shown
- **AND** the citation inspector is not shown

#### Scenario: Usuario turn then staff layout shows that turn's inspector
- **GIVEN** an authenticated session in the end-user layout
- **AND** the user asked an in-corpus question that produced two citations and eighteen guardrail rows
- **WHEN** the user selects the staff layout
- **THEN** the citation inspector shows the first of those two citations
- **AND** the trust panel shows the eighteen rows of that turn, not "Sin guardrails todavía."

### Requirement: Trust panel and abstain banner
The staff layout SHALL show the per-query guardrail log as chips grouped by stage (`input`, `retrieve`, `generate`, `output`) with verdicts `pass`, `warn`, `block`, `redact`, or `skipped`, and SHALL show whether each rule was enforced and whether it would have blocked. A verdict outside that set SHALL render with the `skipped` style. While a turn is in progress the citation card SHALL read "Buscando citas…" and the trust panel "Guardrails en curso…" until the answer arrives; the previous turn's chips MUST NOT remain under the pending row. In both layouts the interface SHALL show an abstain banner in the chat stage when finding is silencio. The end-user layout SHALL NOT show the guardrail log.

#### Scenario: Silencio banner
- **GIVEN** the staff layout
- **AND** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible in the chat stage
- **AND** the named guardrail appears in the panel as a chip

#### Scenario: In-corpus trust panel
- **GIVEN** the staff layout
- **AND** an in-corpus answer with all enabled rules passing
- **WHEN** the answer is rendered
- **THEN** the trust panel lists those rules as pass, warn, or redact chips
- **AND** retrieve and generate steps are present

#### Scenario: Jailbreak skipped tail
- **GIVEN** the staff layout
- **AND** the user submits a jailbreak
- **WHEN** the answer is rendered
- **THEN** the injection chip is `block`
- **AND** retrieve and generate chips are `skipped`

#### Scenario: Pending turn shows in-progress placeholders
- **GIVEN** the staff layout with a prior answered turn
- **WHEN** the user sends a new question
- **THEN** before the answer arrives the citation card reads "Buscando citas…"
- **AND** the trust panel reads "Guardrails en curso…"
- **AND** the prior turn's chips are not shown

#### Scenario: Unknown verdict is not green
- **GIVEN** a guardrail row whose verdict is the string `weird`
- **WHEN** the trust panel is rendered
- **THEN** that chip uses the `skipped` style

#### Scenario: End-user layout hides the trust log
- **GIVEN** an in-corpus answer with all enabled rules passing
- **WHEN** the user selects the end-user layout
- **THEN** the guardrail log is not shown
- **AND** the conversation still shows the answer

#### Scenario: Shadow would-block is visible to staff
- **GIVEN** the staff layout
- **AND** a rule is configured not to enforce
- **AND** that rule would have blocked
- **WHEN** the answer is rendered
- **THEN** the trust panel shows that the rule was not enforced
- **AND** that it would have blocked

### Requirement: Limit notice on the assistant
When a turn is refused with HTTP 401 or 429, the conversation SHALL show the existing Spanish notice as the assistant row, the pending thinking row SHALL be removed, and the citation inspector and trust panel SHALL keep the content of the last answered turn. When a turn fails for any other reason, the pending row SHALL be replaced by "Error interno al responder. Probá de nuevo.", the inspector and trust panel SHALL be reset to their empty states, and the interface MUST NOT surface a raw exception.

#### Scenario: Limit keeps the prior inspector
- **GIVEN** the staff layout with a prior answered turn whose card names `A8359`
- **WHEN** the next turn is refused with HTTP 429
- **THEN** the conversation shows "Demasiados intentos. Probá más tarde."
- **AND** the citation card still names `A8359`

#### Scenario: Internal failure resets the inspector
- **GIVEN** the staff layout
- **AND** the turn runner raises a non-HTTP exception
- **WHEN** the turn ends
- **THEN** the assistant row reads "Error interno al responder. Probá de nuevo."
- **AND** the citation card reads "Todavía no hay citas en esta consulta."
- **AND** no exception escapes to the interface

#### Scenario: Daily cap shows Spanish notice
- **GIVEN** an authenticated session that has reached the email language-model cap
- **WHEN** the user sends a question
- **THEN** the language model is not called
- **AND** a Spanish notice tells them there were too many attempts

### Requirement: Observatory shell
The assistant interface SHALL be one screen with a topbar, a dominant chat stage, and a footer. In the staff layout it SHALL also show a side inspector. The topbar SHALL show that the corpus is a BCRA CAMEX unofficial extract. In the staff layout the topbar SHALL also show `to_as_of`, `last_refresh`, last Comunicación id, and document count as chips without opening a settings page. The chat stage SHALL hold the conversation, the question input, suggested prompts, send, Clear, and the abstain banner when it applies. In the staff layout the side inspector SHALL hold citation cards, the this-query trust log, and the Calidad L1 section. The end-user layout SHALL NOT show the side inspector. The footer SHALL state that the extract is unofficial, not BCRA, not legal advice, and dated as of `last_refresh`. When the side inspector is visible, on a wide viewport the chat stage SHALL sit to the left of the inspector and the inspector SHALL stay in view while the chat scrolls, scrolling internally when it is taller than the viewport; on a narrow viewport the inspector SHALL sit below the chat stage and the page SHALL be the only scroller.

#### Scenario: Freeze chips on load
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464, and a document count
- **WHEN** the interface loads
- **THEN** the topbar shows those values as chips

#### Scenario: Tall inspector on a short desktop viewport
- **GIVEN** the staff layout on a 1280×800 viewport
- **AND** a trust panel of eighteen rows that is taller than the viewport
- **WHEN** the user scrolls the chat
- **THEN** the inspector stays pinned below the topbar
- **AND** the inspector itself can be scrolled to reach Calidad L1

#### Scenario: Phone keeps one scroller
- **GIVEN** a 375×812 viewport
- **WHEN** the staff layout is shown
- **THEN** the inspector sits below the chat stage
- **AND** it has no internal scrollbar

#### Scenario: Wide layout keeps chat dominant
- **GIVEN** the staff layout
- **AND** the interface is shown on a wide viewport
- **WHEN** the user looks at the screen
- **THEN** the chat stage is on the left
- **AND** the inspector is on the right

#### Scenario: Narrow layout stacks the inspector
- **GIVEN** the staff layout
- **AND** the interface is shown on a narrow viewport
- **WHEN** the user looks at the screen
- **THEN** the inspector sits below the chat stage
- **AND** chat, citations, and trust remain on the same screen

#### Scenario: Silencio banner stays in the chat stage
- **GIVEN** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible in the chat stage

#### Scenario: Clear still drops prior turns
- **GIVEN** a session with prior turns
- **WHEN** the user clicks Clear
- **THEN** the next question does not use those turns

#### Scenario: End-user layout hides the side inspector
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at the screen
- **THEN** the side inspector is not shown
- **AND** the chat stage, footer, and management control remain visible

## ADDED Requirements

### Requirement: Send-code status is true on every success
After the user requests a one-time secret, the success status shown on HTTP 200 SHALL be wording that is true whether a new secret was mailed, a still-valid secret already existed, or the address is not enabled: it SHALL tell the user to reuse a code requested within the coalesce window and otherwise to check their mail, and it SHALL state that window in minutes derived from the configured secret lifetime. The status MUST NOT differ between those three cases.

#### Scenario: Second request inside the window
- **GIVEN** the user requested a secret 2 minutes ago with a 5-minute lifetime
- **WHEN** the user requests again
- **THEN** the status reads "Listo. Si pediste un código hace menos de 5 minutos, usá ese; si no, revisá tu correo."
- **AND** the same wording is used for a first request

#### Scenario: Window follows the configured lifetime
- **GIVEN** a 10-minute secret lifetime
- **WHEN** the interface is built
- **THEN** the success status names 10 minutes
