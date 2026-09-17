## ADDED Requirements

### Requirement: Citations carry dump metadata
After citations are validated, the system SHALL fill each citation's `fecha` and `url` from the dump manifest entry of that document (the texto ordenado URL for `texto_ordenado`) when the model did not provide them, and SHALL fill `punto` from the cited chunk's metadata when the model omitted it. The language model is not asked to produce `fecha` or `url`.

#### Scenario: Comunicación citation gets date and link
- **GIVEN** the manifest entry for `A8464` has `fecha` 2026-08-06 and a `bcra.gob.ar` URL
- **AND** the model cites `A8464` with a valid snippet and no `fecha`
- **WHEN** the response is finalized
- **THEN** the citation `fecha` is 2026-08-06
- **AND** the citation `url` is that manifest URL

#### Scenario: Texto ordenado citation gets its URL and punto
- **GIVEN** the model cites `texto_ordenado` with a valid snippet and no punto
- **AND** the anchoring chunk has punto 3.8.5
- **WHEN** the response is finalized
- **THEN** the citation `url` is the texto ordenado PDF URL
- **AND** the citation `punto` is 3.8.5

### Requirement: Context chunk cap is configured
The number of characters of each retrieved chunk placed in the prompt, and the size of a fetched named section, SHALL be bounded by `CONTEXT_CHUNK_CHARS` (default 3000, at least 500). The context-budget rail keeps its own total bound.

#### Scenario: Default cap
- **GIVEN** default settings and a 5000-character section
- **WHEN** the prompt is built
- **THEN** that section contributes at most 3000 characters
