## ADDED Requirements

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
