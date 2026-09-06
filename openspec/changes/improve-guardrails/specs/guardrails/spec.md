## MODIFIED Requirements

### Requirement: Per-query guardrail log
Every chat response SHALL include a guardrail log listing each enabled rule for that turn with verdict `pass`, `warn`, `block`, `redact`, or `skipped`, a short detail, a stage (`input`, `retrieve`, `generate`, or `output`), whether the rule was enforced, and whether it would have blocked if enforced. Work that did not run SHALL be `skipped` and MUST NOT be stamped `pass`. The staff assistant interface MUST show that log next to the answer.

#### Scenario: Demo lights different rules
- **GIVEN** an in-corpus question, a jailbreak, and “should I buy dollars”
- **WHEN** each is submitted
- **THEN** the log names different blocking or passing rules
- **AND** the in-corpus path can show every enabled rule as pass, warn, or redact

#### Scenario: Jailbreak does not fake-pass retrieve
- **GIVEN** a prompt that asks to ignore previous instructions and reveal the system prompt
- **WHEN** it is submitted
- **THEN** the injection rule is `block`
- **AND** retrieve and generate steps are `skipped`
- **AND** no retrieve step is stamped `pass`

### Requirement: Cite or abstain
A non-abstain answer MUST include at least one citation whose id exists in **this turn’s** retrieved dump documents (Comunicación or texto ordenado id, not an internal chunk id) and whose quoted span is a whitespace-normalized substring of that retrieved text. Otherwise the system SHALL force finding `silencio` and empty citations and MUST NOT show the draft.

#### Scenario: Missing citation becomes silencio
- **GIVEN** generation would answer without a dump id retrieved this turn
- **WHEN** the response is finalized
- **THEN** finding is silencio
- **AND** citations are empty

#### Scenario: Quote not in the cited document becomes silencio
- **GIVEN** generation cites a dump id retrieved this turn with a quote that is not in that document’s retrieved text
- **WHEN** the response is finalized
- **THEN** finding is silencio
- **AND** citations are empty

### Requirement: Injection
The system SHALL block prompt-injection attempts to reveal or override hidden instructions, including Spanish paraphrases and hidden-character obfuscation. Hidden instructions SHALL stay hidden. Blocked turns SHALL name the injection rule, SHALL use finding `silencio`, SHALL NOT retrieve, and SHALL NOT call the language model.

#### Scenario: Jailbreak is blocked
- **GIVEN** a prompt that asks to ignore previous instructions and reveal the system prompt
- **WHEN** it is submitted
- **THEN** the injection rule is `block`
- **AND** finding is silencio
- **AND** the response does not reveal hidden instructions
- **AND** the language model is not called

#### Scenario: Hidden-character jailbreak is blocked
- **GIVEN** a jailbreak whose payload is wrapped in zero-width or bidi override characters
- **WHEN** it is submitted
- **THEN** the injection rule is `block`
- **AND** the language model is not called

### Requirement: No advice
The system SHALL refuse investment advice, including whether to buy dollars or where to park pesos, on the user question **and** on the generated answer. A blocked question SHALL NOT retrieve and SHALL NOT call the language model. A blocked answer SHALL use finding `silencio` and MUST NOT show the draft.

#### Scenario: Should I buy dollars
- **GIVEN** the user asks “Deberia comprar dolares?”
- **WHEN** the request is processed
- **THEN** the no-advice rule is `block`
- **AND** finding is silencio
- **AND** the language model is not called

#### Scenario: Advice in the answer is blocked
- **GIVEN** an in-scope question whose generated answer recommends buying dollars
- **WHEN** the response is finalized
- **THEN** finding is silencio
- **AND** the draft is not shown

## ADDED Requirements

### Requirement: Retrieved documents are scanned
The system SHALL inspect each retrieved document before generation. A document that carries hidden instructions or role-override markup SHALL be dropped. If no document survives, the system SHALL use finding `silencio` and SHALL NOT call the language model.

#### Scenario: Planted instructions do not appear in the answer
- **GIVEN** retrieval would return a document that says to ignore previous instructions
- **WHEN** the user asks an in-corpus question that would retrieve it
- **THEN** that document is not used as a citation
- **AND** if no other document survives, finding is silencio
- **AND** the language model is not called when none survive

### Requirement: Secrets and unsafe output
The system SHALL block secret-shaped tokens (API keys) in the question and in the answer without repeating the token in the guardrail detail. The system SHALL strip or neutralize ANSI control sequences, tool-shaped tags, raw HTML, `javascript:` / `data:` links, and markdown images in the visible answer. Links that are not official `bcra.gob.ar` HTTPS URLs SHALL be neutralized.

#### Scenario: Secret in the query is blocked
- **GIVEN** the user question contains an `sk-` shaped token
- **WHEN** the request is processed
- **THEN** finding is silencio
- **AND** the language model is not called
- **AND** the guardrail detail does not contain that token

### Requirement: Shadow mode
A rule MAY be configured not to enforce. The system SHALL still run it, SHALL record `would_block` when it would have blocked, SHALL keep the enforced verdict `pass`, and MUST NOT change the user-visible answer solely because of that rule.

#### Scenario: Shadow injection does not block
- **GIVEN** injection is configured not to enforce
- **AND** the user submits a jailbreak
- **WHEN** the request is processed
- **THEN** the injection log row has `would_block` true
- **AND** the enforced verdict is not `block`

### Requirement: Follow-up is railed
Input rules other than length SHALL run on the composed follow-up text used for retrieval, not only the raw latest message.

#### Scenario: Follow-up jailbreak is blocked
- **GIVEN** a session with a prior in-corpus question
- **WHEN** the user sends a short follow-up that asks to ignore previous instructions
- **THEN** the injection rule is `block`
- **AND** the language model is not called
