## ADDED Requirements

### Requirement: Turn evaluation is logged after the response
When per-turn evaluation is enabled and the language model was called, the `chat_turn_eval` record SHALL be written when background scoring completes, carrying the request id of the turn and the scores, and MAY appear after the `chat_turn` record of the same request id.

#### Scenario: Eval record follows the turn record
- **GIVEN** per-turn evaluation is enabled
- **WHEN** an in-corpus question is answered
- **THEN** a `chat_turn` record is written when the response is returned
- **AND** a `chat_turn_eval` record with the same request id is written when scoring finishes
