# assistant-ui Specification

## Purpose

Give staff one screen with cited clauses, a this-query trust panel, and last-run L1, and give end users a reduced chat layout on that same screen — without a second product UI.

## Requirements

### Requirement: Banner
The assistant interface SHALL show that the corpus is a BCRA CAMEX unofficial extract. The always-visible title SHALL name BCRA CAMEX and that the extract is unofficial. In the staff layout it SHALL also show `to_as_of`, `last_refresh`, last Comunicación id, and document count without opening a settings page. Those dump freeze chips SHALL NOT be shown in the end-user layout.

#### Scenario: Banner after ingest
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the interface loads
- **THEN** those values are visible without opening a settings page
- **AND** the unofficial CAMEX extract wording is visible
- **AND** the visible title names BCRA CAMEX

#### Scenario: Freeze chips hidden in end-user layout
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the user selects the end-user layout
- **THEN** `to_as_of`, `last_refresh`, last Comunicación id, and document count are not shown as freeze chips
- **AND** the unofficial CAMEX extract wording remains visible
- **AND** the visible title still names BCRA CAMEX

### Requirement: Observatory shell
The assistant interface SHALL be one screen with a topbar, a dominant chat stage, and a footer. In the staff layout it SHALL also show a side inspector. The topbar SHALL show that the corpus is a BCRA CAMEX unofficial extract. In the staff layout the topbar SHALL also show `to_as_of`, `last_refresh`, last Comunicación id, and document count as chips without opening a settings page. The chat stage SHALL hold the conversation, the question input, suggested prompts, send, Clear, and the abstain banner when it applies. In the staff layout the side inspector SHALL hold citation cards, the this-query trust log, and the Calidad L1 section. The end-user layout SHALL NOT show the side inspector. The footer SHALL state that the extract is unofficial, not BCRA, not legal advice, and dated as of `last_refresh`. When the side inspector is visible, on a wide viewport the chat stage SHALL sit to the left of the inspector, and on a narrow viewport the inspector SHALL sit below the chat stage.

#### Scenario: Freeze chips on load
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464, and a document count
- **WHEN** the interface loads
- **THEN** the topbar shows those values as chips
- **AND** the unofficial CAMEX extract wording is visible
- **AND** no settings page is required

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

### Requirement: Editorial observatory chrome
The assistant interface SHALL use a navy background, gold primary actions, blue links, kicker labels, and pill badges on that one screen. Suggested prompts SHALL appear as pills whose text is the existing canned mix (tipo de cambio de referencia A 3500/A 8359, liquidación de exportaciones, a 2001–2002 superseded-trap, and Com. A 9999). Chat and prompts MUST remain usable without opening a second page. In the staff layout, citations and trust MUST remain usable on that same screen.

#### Scenario: Suggested prompts remain pills on the stage
- **GIVEN** the interface is shown
- **WHEN** the user looks at suggested prompts
- **THEN** they appear as pills on the chat stage
- **AND** three prompts are answerable from the dump
- **AND** one asks for a comunicación that is not in the dump
- **AND** none is a generic “explain the BCRA”

#### Scenario: One screen remains usable
- **GIVEN** the staff layout
- **WHEN** the user asks a named Com. A that is in the dump
- **THEN** the answer, citation cards, and trust log are on the same screen
- **AND** the interface does not open a second product UI

#### Scenario: End-user layout stays one screen
- **GIVEN** the end-user layout
- **WHEN** the user asks a named Com. A that is in the dump
- **THEN** the answer is on the same screen as the question input
- **AND** the interface does not open a second product UI

#### Scenario: Navy editorial chrome is visible
- **GIVEN** the interface is shown
- **WHEN** the user looks at the screen
- **THEN** the page background is navy
- **AND** the primary send action is gold
- **AND** links are blue

### Requirement: Chat and canned prompts
The interface SHALL provide a chat input, three suggested prompts that are answerable from the dump (tipo de cambio de referencia A 3500/A 8359, liquidación de exportaciones, and a 2001–2002 superseded-trap), and one out-of-corpus prompt (Com. A 9999).

#### Scenario: Suggested prompts mix answerable and silencio
- **GIVEN** the interface is shown
- **WHEN** the user looks at suggested prompts
- **THEN** three prompts are answerable from the dump
- **AND** one asks for a comunicación that is not in the dump
- **AND** none is a generic “explain the BCRA”

### Requirement: Citation inspector
In the staff layout the interface SHALL show citation cards as the visible inspector, with Comunicación id, fecha, punto when known, a short snippet, a copy-id action, and the official bcra.gob.ar PDF URL. A raw structured dump MUST NOT be the primary inspector surface. Clicking a card SHALL update the inspector, not navigate away. Copy-id SHALL place the dump document id on the clipboard (for example A8359), matching the citation id. The end-user layout SHALL NOT show that inspector.

#### Scenario: Citation card
- **GIVEN** the staff layout
- **AND** an answer that cites A 8359
- **WHEN** the user inspects citations
- **THEN** they see A 8359, its date, a snippet, and a bcra.gob.ar link
- **AND** the visible inspector is the citation cards, not a raw structured dump

#### Scenario: Copy id
- **GIVEN** the staff layout
- **AND** a citation card for A 8359
- **WHEN** the user uses copy-id
- **THEN** the dump id A8359 is placed on the clipboard

#### Scenario: Click stays in inspector
- **GIVEN** the staff layout
- **AND** an answer that cites A 8359
- **WHEN** the user clicks that citation card
- **THEN** the inspector updates to A 8359
- **AND** the interface does not navigate away from the assistant

#### Scenario: End-user layout hides the inspector
- **GIVEN** an answer that cites A 8359
- **WHEN** the user selects the end-user layout
- **THEN** citation cards, copy-id, and the inspector are not shown

### Requirement: Trust panel and abstain banner
The staff layout SHALL show the per-query guardrail log as chips grouped by stage (`input`, `retrieve`, `generate`, `output`) with verdicts `pass`, `warn`, `block`, `redact`, or `skipped`, and SHALL show whether each rule was enforced and whether it would have blocked. In both layouts the interface SHALL show an abstain banner in the chat stage when finding is silencio. The end-user layout SHALL NOT show the guardrail log.

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

### Requirement: L1 accordion
In the staff layout the interface SHALL include a “Calidad L1” section that starts collapsed and renders the last static L1 results when expanded. It MUST NOT run evals in the browser. The expanded section SHALL show two headings, retrieval and generation, when those blocks exist. A skipped suite SHALL be labeled skipped and MUST NOT be shown as a score of 0. If the stored file is labeled unpublished or sample, the expanded section SHALL say the numbers are a sample and not an operator run. That banner SHALL remain whenever the stored file is labeled unpublished or sample. After the serving process reloads, the expanded section SHALL show the stored document as-is. The end-user layout SHALL NOT show Calidad L1.

#### Scenario: Accordion starts collapsed
- **GIVEN** the interface has just loaded
- **WHEN** the user has not expanded Calidad L1
- **THEN** the L1 numbers are not shown in the main chat column

#### Scenario: Accordion is static
- **GIVEN** the staff layout
- **AND** a stored L1 results file
- **WHEN** the user expands Calidad L1
- **THEN** citation-id exact, hit@5, and A vs B from that file are shown
- **AND** retrieval and generation headings are shown when those blocks exist
- **AND** no eval request is sent to a model from the client

#### Scenario: Unpublished fixture is labeled
- **GIVEN** the staff layout
- **AND** only the shipped unpublished L1 results exist
- **WHEN** the user expands Calidad L1
- **THEN** the section states that the numbers are a sample or unpublished

#### Scenario: Skipped generation is not zero
- **GIVEN** the staff layout
- **AND** the stored L1 results mark generation skipped
- **WHEN** the user expands Calidad L1
- **THEN** generation is labeled skipped
- **AND** faithfulness is not shown as 0

#### Scenario: Published dump-host run has no sample banner
- **GIVEN** the staff layout
- **AND** the dump index was ready
- **AND** the stored L1 results are not labeled unpublished or sample
- **AND** the serving process has reloaded after a dump-host operator L1 run
- **WHEN** the user expands Calidad L1
- **THEN** the stored operator numbers are shown
- **AND** the section does not state that the numbers are a sample or unpublished
- **AND** retrieval and generation headings are shown when those blocks exist

#### Scenario: Sample banner survives reload when unpublished
- **GIVEN** the staff layout
- **AND** the stored L1 results are labeled unpublished or sample
- **AND** the serving process has reloaded
- **WHEN** the user expands Calidad L1
- **THEN** the section states that the numbers are a sample or unpublished

#### Scenario: End-user layout hides Calidad L1
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at the screen
- **THEN** Calidad L1 is not shown

### Requirement: Unauthenticated send does not query
The assistant interface SHALL NOT produce a CAMEX answer, silencio clause, thinking trace, or citation inspector update from Enviar, Enter, Clear, or a canned prompt while the client is not authenticated. The user SHALL see a Spanish notice that they must sign in. The language model MUST NOT be called. Clear while unauthenticated MUST keep prior conversation turns and MUST NOT empty the conversation.

#### Scenario: Enviar while logged out
- **GIVEN** the interface is shown without a session
- **WHEN** the user sends a question
- **THEN** the language model is not called
- **AND** a Spanish notice tells them to sign in
- **AND** the citation inspector is not shown

#### Scenario: Clear while logged out
- **GIVEN** the interface is shown without a session
- **AND** prior conversation turns are visible
- **WHEN** the user clicks Clear
- **THEN** the language model is not called
- **AND** a Spanish notice tells them to sign in
- **AND** those prior turns remain

### Requirement: Clear
The interface SHALL provide a Clear control labeled Limpiar and SHALL treat typed `/clear` as the same action. Session id SHALL persist across turns in the same UI session until cleared.

#### Scenario: Clear button
- **GIVEN** a session with prior turns
- **WHEN** the user clicks Clear
- **THEN** the next question does not use those turns

#### Scenario: Clear is labeled Limpiar
- **GIVEN** the interface is shown
- **WHEN** the user looks at the Clear control
- **THEN** the visible label is Limpiar

#### Scenario: Session id persists
- **GIVEN** the interface has minted a session id
- **WHEN** the user sends a second question without clearing
- **THEN** that question uses the same session id

### Requirement: Layout toggle
The assistant interface SHALL provide a management control that switches between a staff layout and an end-user layout without leaving the assistant. The default on load SHALL be the end-user layout, including when a valid session exists. The control SHALL remain visible in both layouts. A visible label next to the control SHALL name both layouts and SHALL state that staff shows the citation inspector, the per-query guardrail log, Calidad L1, and dump freeze dates, and that end-user keeps the question, the answer, send, Clear, and suggested prompts. Switching layout MUST NOT clear the conversation or the session. Selecting the staff layout SHALL apply staff chrome only when the client is authenticated; when the client is not authenticated, freeze chips, the side inspector, the trust log, Calidad L1, and thinking MUST stay hidden and the conversation MUST remain on the end-user layout.

#### Scenario: Default load is staff
- **GIVEN** a dump with last_refresh 2026-09-01, to_as_of A 8307, last A 8464
- **WHEN** the interface loads
- **THEN** freeze chips, citation inspector chrome, the trust panel, and Calidad L1 are not shown
- **AND** the question input, send, Clear, and suggested prompts are visible
- **AND** the unofficial CAMEX extract wording is visible
- **AND** Calidad L1 is not expanded into the main chat column

#### Scenario: Authenticated reload still defaults to end-user
- **GIVEN** a valid session
- **WHEN** the interface loads
- **THEN** the end-user layout is shown
- **AND** selecting the staff layout reveals freeze chips and the side inspector without a new one-time secret

#### Scenario: Unauthenticated staff selection does not reveal chrome
- **GIVEN** the interface is shown without a session
- **WHEN** the user selects the staff layout
- **THEN** freeze chips, citation inspector chrome, the trust panel, Calidad L1, and thinking are not shown
- **AND** the management control remains visible
- **AND** the interface does not navigate away from the assistant

#### Scenario: Label names both layouts and what changes
- **GIVEN** the interface is shown
- **WHEN** the user looks at the management control
- **THEN** a visible label names the staff layout and the end-user layout
- **AND** the label states that staff shows the citation inspector, the guardrail log, Calidad L1, and dump freeze dates
- **AND** the label states that end-user keeps the question, the answer, send, Clear, and suggested prompts

#### Scenario: Switch to end-user hides debug chrome
- **GIVEN** an authenticated session
- **AND** the interface is in the staff layout
- **WHEN** the user selects the end-user layout
- **THEN** the citation inspector, the guardrail log, Calidad L1, and dump freeze chips are not shown
- **AND** the question input, conversation, send, Clear, and suggested prompts remain
- **AND** the management control and its label remain visible

#### Scenario: Switch back restores staff chrome
- **GIVEN** an authenticated session
- **AND** the interface is in the end-user layout
- **WHEN** the user selects the staff layout
- **THEN** freeze chips, citation inspector chrome, the trust panel, and Calidad L1 are present again
- **AND** the interface does not navigate away from the assistant

#### Scenario: Layout switch keeps the session
- **GIVEN** an authenticated session with prior turns
- **WHEN** the user switches from staff to end-user layout without clearing
- **THEN** those turns remain in the conversation
- **AND** a later question without Clear uses the same session

### Requirement: Thinking in the output box
The chat stage SHALL show a thinking region in the conversation output box that is visually distinct from the assistant answer (muted relative to the answer, not the same bubble). That region SHALL appear in the staff layout. The end-user layout SHALL NOT show the thinking region. While a turn is in flight, the thinking region SHALL show live motion (a spinner and/or pulse) so the user can tell work is happening. While the language model is producing a reasoning trace, the thinking region SHALL show that trace text as it is received, before the cited answer appears — not only a title or label. After the turn completes, that region SHALL remain expanded and collapsible. Prior turns MAY keep their thinking region collapsed. The cited answer, silencio text, and `Fuente:` line MUST NOT appear inside the thinking region. When `thinking` is absent, empty, or null, the conversation SHALL NOT leave an empty thinking region; the answer or silencio text SHALL still appear. The thinking region MUST NOT replace the cited answer, the `Fuente:` line, or the abstain banner. Clear SHALL drop prior turns including any thinking region. Switching layout MUST NOT clear the thinking region of the current conversation; the end-user layout SHALL hide it and the staff layout SHALL show it again.

#### Scenario: Pending motion on send
- **GIVEN** the interface is shown in the staff layout
- **WHEN** the user sends a question
- **THEN** the output box shows a thinking region with live motion before the cited answer or silencio appears

#### Scenario: Trace is distinct from the cited answer
- **GIVEN** the index is ready
- **AND** the language-model provider returns a reasoning trace with a cited JSON answer
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the thinking region shows that trace text, not only a title or label
- **AND** the assistant answer bubble shows the cited clause with a `Fuente:` line
- **AND** the thinking region and the answer are visually distinct
- **AND** the cited clause and `Fuente:` line are not inside the thinking region

#### Scenario: Trace appears as it is received
- **GIVEN** the index is ready
- **AND** the language-model provider emits a reasoning trace before the cited JSON answer
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the thinking region shows that trace text while the turn is still in flight
- **AND** the cited answer is not yet in the conversation
- **AND** after the turn completes the thinking region stays expanded and collapsible
- **AND** the cited answer appears below the thinking region, not inside it

#### Scenario: Named Com. A still answers in chat
- **GIVEN** Comunicación A 8359 is in the dump
- **AND** the language-model provider returns a reasoning trace
- **WHEN** the user asks what Comunicación A 8359 says
- **THEN** the conversation shows the answer
- **AND** the thinking region is above that answer
- **AND** the thinking region is not the citation inspector

#### Scenario: No leftover thinking when the model is not called
- **GIVEN** the interface is shown
- **AND** finding will be silencio without a language-model call (empty retrieval or a blocking guardrail)
- **WHEN** the user asks that question
- **THEN** the conversation shows the silencio answer
- **AND** the output box does not leave an empty thinking region

#### Scenario: No leftover thinking when the provider has no trace
- **GIVEN** the index is ready
- **AND** the language-model provider returns a cited JSON answer and no reasoning trace
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the conversation shows the answer
- **AND** the output box does not leave an empty thinking region

#### Scenario: Staff layout shows thinking; end-user layout hides it
- **GIVEN** a turn whose response includes a thinking trace
- **WHEN** the user is in the staff layout
- **THEN** the thinking region is in the chat stage
- **WHEN** the user selects the end-user layout without clearing
- **THEN** the thinking region is not shown
- **AND** the cited answer remains
- **AND** the citation inspector is not shown
- **WHEN** the user selects the staff layout again without clearing
- **THEN** the thinking region is shown again

#### Scenario: Clear drops thinking
- **GIVEN** a session whose conversation includes a thinking region
- **WHEN** the user clicks Clear
- **THEN** the next question does not use those turns
- **AND** the thinking region from the prior turn is gone

### Requirement: Staff payloads stay off the wire in Usuario
When the layout is the end-user layout, or the client is not authenticated, the assistant interface MUST NOT stream a thinking trace into the conversation and MUST NOT fill the citation inspector or the per-query guardrail log for that turn. Authenticated staff layout keeps the existing thinking, inspector, and trust contracts.

#### Scenario: Usuario turn does not stream thinking
- **GIVEN** an authenticated session
- **AND** the interface is in the end-user layout
- **AND** the language-model provider would return a reasoning trace
- **WHEN** the user asks an in-corpus vigente question
- **THEN** the conversation shows the cited answer
- **AND** the thinking region is not shown
- **AND** the citation inspector is not shown

### Requirement: End-user layout
In the end-user layout the interface SHALL show the question input, the conversation, send, Clear, and the four canned prompts (tipo de cambio de referencia A 3500/A 8359, liquidación de exportaciones, a 2001–2002 superseded-trap, and Com. A 9999). It SHALL hide the citation inspector, the per-query guardrail log, and Calidad L1. It SHALL NOT show dump freeze chips (`to_as_of`, `last_refresh`, last Comunicación id, document count). The footer SHALL still state that the extract is unofficial, not BCRA, not legal advice, and dated as of `last_refresh`. When finding is silencio, an abstain banner SHALL remain visible in the chat column.

#### Scenario: End-user surfaces
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at the screen
- **THEN** the question input, conversation, send, Clear, and suggested prompts are visible
- **AND** the citation inspector, the guardrail log, and Calidad L1 are not shown
- **AND** dump freeze chips are not shown
- **AND** the unofficial-extract footer wording is visible

#### Scenario: Suggested prompts remain in end-user layout
- **GIVEN** the interface is in the end-user layout
- **WHEN** the user looks at suggested prompts
- **THEN** three prompts are answerable from the dump
- **AND** one asks for a comunicación that is not in the dump
- **AND** none is a generic “explain the BCRA”

#### Scenario: Silencio banner stays in the chat column
- **GIVEN** the interface is in the end-user layout
- **AND** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible in the chat column
- **AND** the guardrail log is not shown

#### Scenario: Named Com. A still answers in chat
- **GIVEN** the interface is in the end-user layout
- **AND** Comunicación A 8359 is in the dump
- **WHEN** the user asks what Comunicación A 8359 says
- **THEN** the conversation shows the answer
- **AND** the citation inspector is not shown

#### Scenario: Clear still drops prior turns
- **GIVEN** the interface is in the end-user layout
- **AND** a session with prior turns
- **WHEN** the user clicks Clear
- **THEN** the next question does not use those turns

### Requirement: First-screen composer
While the client is not authenticated, the assistant interface SHALL keep the question input and send on the same first screen as the login row. On a wide laptop viewport the question input and send MUST be visible without scrolling away from the login row. The interface MUST NOT open a second product UI.

#### Scenario: Wide viewport keeps send with login
- **GIVEN** the interface is shown without a session
- **AND** the interface is shown on a wide laptop viewport
- **WHEN** the user looks at the screen
- **THEN** an email field and a send-code control are visible
- **AND** the question input and send are visible without scrolling

#### Scenario: Narrow viewport still one screen
- **GIVEN** the interface is shown without a session
- **AND** the interface is shown on a narrow viewport
- **WHEN** the user looks at the screen
- **THEN** an email field and a send-code control are visible
- **AND** the question input remains on the same screen

### Requirement: Login chrome on the same screen
While the client is not authenticated, the assistant interface SHALL show a login row on the same screen: an email field, a control to send the one-time secret, a 6-digit field, a control to verify, and a status message. Copy SHALL be Spanish. While authenticated, that row SHALL hide the request/verify fields and SHALL show the signed-in email plus a logout control. Login and logout MUST NOT open a second product UI. A short confirm step for a mail login link MAY appear and MUST then return to this same assistant screen with the logout control visible. Logout MUST NOT clear the conversation by itself.

#### Scenario: Logged-out load shows login
- **GIVEN** the interface is shown without a session
- **WHEN** the user looks at the screen
- **THEN** an email field and a send-code control are visible
- **AND** the question input remains on the same screen

#### Scenario: Logged-in load shows logout
- **GIVEN** a valid session for `ops@example.com`
- **WHEN** the interface loads
- **THEN** a logout control is visible
- **AND** the request-code fields are not shown

#### Scenario: Logout returns the login row
- **GIVEN** an authenticated session
- **WHEN** the user logs out
- **THEN** the login row is visible again
- **AND** staff chrome is not shown
- **AND** prior conversation turns remain until Clear

#### Scenario: Mail-link session shows logout on the assistant
- **GIVEN** the client authenticated from a login link as `ops@example.com`
- **WHEN** the assistant screen loads
- **THEN** a logout control is visible
- **AND** the request-code fields are not shown
- **AND** the question input remains on the same screen

### Requirement: Mail-link confirm stays an interstitial
When a login link needs confirmation, the system SHALL show a Spanish page that names the mailbox, offers a native confirm control that works without page script, and MUST NOT present a second product assistant. After success or failure the user SHALL be able to reach the existing assistant screen. Typed 6-digit login SHALL remain on the observatory.

#### Scenario: Confirm names the mailbox and works without script
- **GIVEN** a valid unused login token for `ops@example.com`
- **AND** the client did not request that secret in this browser
- **WHEN** the client opens the login URL
- **THEN** the page is in Spanish
- **AND** it names `ops@example.com`
- **AND** a form posts without requiring page script
- **AND** the observatory question input is not replaced by a second product UI

#### Scenario: Typed code remains available
- **GIVEN** the assistant is shown without a session
- **WHEN** the user looks at the login row
- **THEN** the 6-digit field and verify control are still on that screen

### Requirement: Limit notice on the assistant
When Enviar is refused because a send or chat limit was exceeded, the assistant interface SHALL show a Spanish notice that there were too many attempts, MUST NOT produce a CAMEX answer, and MUST NOT call the language model.

#### Scenario: Daily cap shows Spanish notice
- **GIVEN** an authenticated session that has reached the email language-model cap
- **WHEN** the user sends a question
- **THEN** the language model is not called
- **AND** a Spanish notice tells them there were too many attempts
