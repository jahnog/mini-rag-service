## ADDED Requirements

### Requirement: Phase line while a turn is in flight
In both layouts the chat stage SHALL show a single-line phase status under the conversation while a turn is in flight, with the Spanish copy "Buscando en el dump…", "Redactando respuesta…" and "Verificando citas…" for the phases `retrieve`, `generate` and `verify`, and SHALL hide it when the turn ends or fails. In the staff layout the pending thinking region SHALL use the current phase copy as its title, falling back to "Pensando…" before the first phase. The phase line is not a thinking trace and MUST NOT contain model text.

#### Scenario: End user sees progress
- **GIVEN** an authenticated session in the end-user layout
- **WHEN** the user sends an in-corpus question
- **THEN** the phase line shows "Buscando en el dump…" and later "Redactando respuesta…"
- **AND** no thinking region is shown
- **AND** the phase line is hidden once the answer appears

#### Scenario: Staff pending title follows the phase
- **GIVEN** the staff layout
- **WHEN** the language-model call starts
- **THEN** the pending thinking region title reads "Redactando respuesta…"

#### Scenario: Failure hides the phase line
- **GIVEN** a turn that ends with HTTP 429
- **WHEN** the notice is shown
- **THEN** the phase line is hidden

### Requirement: Thinking publish throttle
While the language model streams a reasoning trace, the interface SHALL redraw the pending thinking region at most every 0.5 seconds on a word or punctuation break (or every second regardless of breaks) and MUST NOT redraw when the trace text is unchanged.

#### Scenario: Unchanged trace is not redrawn
- **GIVEN** the provider repeats the same trace text twice
- **WHEN** the interface publishes
- **THEN** only one pending redraw is produced for that text
