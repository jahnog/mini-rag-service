## ADDED Requirements

### Requirement: Guardrail decision fields on the chat turn
Each completed chat turn record SHALL include the policy version, and for every guardrail log row: stage, enforced flag, would-block flag, and latency. It SHALL include dump ids that survived retrieval scanning and dump ids dropped by a document rule. It MUST NOT echo secret-shaped tokens in details. It MUST NOT include the language-model prompt.

#### Scenario: Blocked injection is reconstructable
- **GIVEN** the user submits a jailbreak
- **WHEN** the turn is logged
- **THEN** the record includes injection as `block`
- **AND** `llm_called` is false
- **AND** retrieve is `skipped`
