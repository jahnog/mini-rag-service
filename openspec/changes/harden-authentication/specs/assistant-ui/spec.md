## MODIFIED Requirements

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
