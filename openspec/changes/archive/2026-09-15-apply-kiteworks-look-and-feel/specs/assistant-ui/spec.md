## RENAMED Requirements

- FROM: `### Requirement: Dark observatory chrome`
- TO: `### Requirement: Editorial observatory chrome`

## MODIFIED Requirements

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
