## Purpose

Apply a small set of deterministic rules to every query so a reviewer can see pass, warn, or block on that turn without running an eval suite in the browser.

## ADDED Requirements

### Requirement: Per-query guardrail log
Every chat response SHALL include a guardrail log listing each v1 rule with verdict `pass`, `warn`, or `block` and a short detail. The assistant interface MUST show that log next to the answer.

#### Scenario: Demo lights different rules
- **GIVEN** an in-corpus question, a jailbreak, and “should I buy dollars”
- **WHEN** each is submitted
- **THEN** the log names different blocking or passing rules
- **AND** the in-corpus path can show all listed v1 rules as pass

### Requirement: Cite or abstain
A non-abstain answer MUST include at least one citation whose id exists in the dump as a Comunicación or texto ordenado document id (not an internal chunk id). Otherwise the system SHALL force finding `silencio` and empty citations.

#### Scenario: Missing citation becomes silencio
- **GIVEN** generation would answer without a dump id
- **WHEN** the response is finalized
- **THEN** finding is silencio
- **AND** citations are empty

### Requirement: Freeze honesty
The system SHALL NOT claim “normativa vigente hoy” without qualifying `last_refresh` and `to_as_of`. If the draft was unqualified, the system SHALL rewrite the visible answer so it names those dates, and the freeze-honesty verdict SHALL be `warn`. If the draft already named those dates, the verdict SHALL be `pass`. The same dates SHALL appear on the health document and the UI banner.

#### Scenario: Vigente wording is qualified
- **GIVEN** last_refresh is 2026-09-01 and to_as_of is A 8307
- **WHEN** the user asks what is vigente
- **THEN** the answer names those dates
- **AND** does not state unqualified “vigente hoy”

### Requirement: Scope
The system SHALL block questions outside BCRA CAMEX / Argentine FX regulation. Blocked turns SHALL name the scope rule in the guardrail log, SHALL use finding `silencio`, SHALL NOT retrieve, and SHALL NOT call the language model.

#### Scenario: Weather is out of scope
- **GIVEN** the user asks about the weather in Madrid
- **WHEN** the request is processed
- **THEN** the scope rule is `block`
- **AND** finding is silencio
- **AND** the language model is not called

### Requirement: Injection
The system SHALL block prompt-injection attempts to reveal or override hidden instructions. Hidden instructions SHALL stay hidden. Blocked turns SHALL name the injection rule, SHALL use finding `silencio`, SHALL NOT retrieve, and SHALL NOT call the language model.

#### Scenario: Jailbreak is blocked
- **GIVEN** a prompt that asks to ignore previous instructions and reveal the system prompt
- **WHEN** it is submitted
- **THEN** the injection rule is `block`
- **AND** finding is silencio
- **AND** the response does not reveal hidden instructions
- **AND** the language model is not called

### Requirement: No advice
The system SHALL refuse investment advice, including whether to buy dollars or where to park pesos. Blocked turns SHALL name the no-advice rule, SHALL use finding `silencio`, SHALL NOT retrieve, and SHALL NOT call the language model.

#### Scenario: Should I buy dollars
- **GIVEN** the user asks “Deberia comprar dolares?”
- **WHEN** the request is processed
- **THEN** the no-advice rule is `block`
- **AND** finding is silencio
- **AND** the language model is not called

### Requirement: Retrieval sidecar is not an L1 score
The system SHALL attach a cheap sidecar (top-k ids and scores, citation coverage, grounded flag) on each response. That sidecar MUST NOT be a batch L1 faithfulness score computed in the client.

#### Scenario: Sidecar explains cite-or-abstain
- **GIVEN** a successful retrieval
- **WHEN** the response is returned
- **THEN** the sidecar lists retrieved ids and scores
- **AND** the client does not compute faithfulness
