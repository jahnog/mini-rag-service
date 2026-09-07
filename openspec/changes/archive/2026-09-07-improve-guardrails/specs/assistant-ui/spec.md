## MODIFIED Requirements

### Requirement: Trust panel and abstain banner
The staff layout SHALL show the per-query guardrail log as chips grouped by stage (`input`, `retrieve`, `generate`, `output`) with verdicts `pass`, `warn`, `block`, `redact`, or `skipped`. In both layouts the interface SHALL show an abstain banner in the chat stage when finding is silencio. The end-user layout SHALL NOT show the guardrail log.

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
