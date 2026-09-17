## ADDED Requirements

### Requirement: Timing and reasoning fields on the chat turn
Every chat turn record SHALL include `retrieve_ms` (wall time of routing and retrieval), `llm_ms` (wall time of the language-model call including any retry), `ttft_ms` (time from the request to the first streamed token, 0 when the model was not called), `thinking_chars` (length of the reasoning trace, 0 when absent) and `abstain_reason` (null when the finding is not silencio). Times SHALL be milliseconds rounded to one decimal.

#### Scenario: In-corpus turn logs timings
- **GIVEN** a ready index and a language model that answers
- **WHEN** the user asks an in-corpus question
- **THEN** the chat turn record has `retrieve_ms` and `llm_ms` greater than or equal to 0
- **AND** `abstain_reason` is null

#### Scenario: Blocked turn logs zero model time
- **GIVEN** an out-of-scope question
- **WHEN** the turn is logged
- **THEN** `llm_ms` and `ttft_ms` are 0
- **AND** `abstain_reason` names the blocking rule
