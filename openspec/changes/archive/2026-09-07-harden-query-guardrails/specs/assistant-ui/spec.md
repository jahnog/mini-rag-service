## MODIFIED Requirements

### Requirement: Trust panel and abstain banner
The staff layout SHALL show the per-query guardrail log as chips grouped by stage (`input`, `retrieve`, `generate`, `output`) with verdicts `pass`, `warn`, `block`, `redact`, or `skipped`, and SHALL show whether each rule was enforced and whether it would have blocked. In both layouts the interface SHALL show an abstain banner in the chat stage when finding is silencio. The end-user layout SHALL NOT show the guardrail log.

#### Scenario: Silencio banner
- **GIVEN** finding is silencio for A 9999
- **WHEN** the answer is rendered
- **THEN** an abstain banner is visible in the chat stage
- **AND** the named guardrail appears in the panel as a chip

#### Scenario: In-corpus trust panel
- **GIVEN** an in-corpus answer with all v1 guardrails passing
- **WHEN** the answer is rendered
- **THEN** the trust panel shows those rules as pass chips

#### Scenario: Shadow would-block is visible to staff
- **GIVEN** the staff layout
- **AND** a rule is configured not to enforce
- **AND** that rule would have blocked
- **WHEN** the answer is rendered
- **THEN** the trust panel shows that the rule was not enforced
- **AND** that it would have blocked
