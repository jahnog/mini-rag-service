# retrieval Specification

## Purpose

Retrieve the right CAMEX clause or document for a question: named Comunicación lookup, vigente routing to current law plus later patches, and measured chunking A versus B.

## Requirements

### Requirement: Two chunking strategies
The system SHALL index documents with a fixed-size chunking strategy (A) and a structure-aware strategy that splits on numbered puntos and sections (B). Strategy B MUST be applied to the texto ordenado and to later documents whose extract already contains clean numbered puntos. Older or messy extracts MAY use only strategy A.

#### Scenario: TO is structure-aware
- **GIVEN** the Exterior y Cambios texto ordenado
- **WHEN** it is indexed
- **THEN** clauses are retrievable by numbered punto (for example 3.8.5)

#### Scenario: Named historical A still indexed
- **GIVEN** a 1983 CAMEX A without clean numbered puntos
- **WHEN** it is indexed
- **THEN** it is still searchable for named-document lookup using strategy A

### Requirement: Chunks fit the embedding input limit
The system SHALL index only chunks whose text fits the configured embedding input limit. Strategy B MUST still split on numbered puntos and sections. When a single punto or section exceeds that limit, the system SHALL store multiple chunks for that unit and SHALL keep the same punto identifier on each part. Strategy A MUST still cover documents without clean numbered puntos, including a named historical Comunicación A.

#### Scenario: Oversized punto stays retrievable by number
- **GIVEN** the texto ordenado contains a numbered punto whose text exceeds the configured embedding input limit
- **WHEN** it is indexed
- **THEN** that punto is stored as more than one chunk
- **AND** each of those chunks still identifies the same numbered punto

#### Scenario: Named historical A still indexed
- **GIVEN** a 1983 CAMEX A without clean numbered puntos
- **AND** a passage longer than the configured embedding input limit
- **WHEN** it is indexed
- **THEN** it is still searchable for named-document lookup using strategy A
- **AND** no stored chunk exceeds the configured embedding input limit

### Requirement: Exclude back-matter unless asked
The system SHALL NOT retrieve correlaciones, origen-de-las-disposiciones, or historial material for an ordinary question. Those parts MAY be retrieved only when the user asks for origen, historial, or correlaciones. Skip SHALL use the chunk heading or body text at retrieval time and MUST NOT require a stored part label from ingest.

#### Scenario: Ordinary question skips correlaciones
- **GIVEN** the TO contains a correlaciones table
- **WHEN** the user asks a vigente rule question
- **THEN** citations are not taken from correlaciones or historial

### Requirement: Named Comunicación fetch
When the user names a Comunicación “A” by number, the system SHALL fetch that document if it is in the dump, and SHALL return silencio if it is not. Named lookup SHALL take precedence over vigente intent. When the response cites that Comunicación, the citation id SHALL be the dump document id (for example A3500), not an internal chunk id. When that Comunicación is in the dump and the language-model draft is not silencio and already names that dump id (as a citation id or in the answer), the response SHALL cite that dump id even if the model’s snippet field is paraphrased or empty; the published snippet SHALL be a verbatim substring of the fetched section.

#### Scenario: A 3500 is in the dump
- **GIVEN** Comunicación A 3500 is in the manifest
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the response cites A 3500
- **AND** the citation id is the dump id A3500

#### Scenario: Named A 3500 paraphrased snippet still cites
- **GIVEN** Comunicación A 3500 is in the manifest
- **AND** the language-model draft cites `A3500` with a paraphrased snippet
- **WHEN** the user asks what Comunicación A 3500 says
- **THEN** the response cites dump id `A3500`
- **AND** finding is not silencio

#### Scenario: Invented Comunicación is silencio
- **GIVEN** Comunicación A 9999 is not in the manifest
- **WHEN** the user asks what Comunicación A 9999 says
- **THEN** finding is silencio
- **AND** citations are empty
- **AND** the answer names `last_refresh`

### Requirement: Truncated extract without punto
If the user names a Comunicación without a punto, the system SHALL return an extract of that document in document order, bounded by `CONTEXT_CHUNK_CHARS`, not an entire texto ordenado.

#### Scenario: Named A without punto is truncated
- **GIVEN** Comunicación A 3500 is in the dump
- **WHEN** the user asks what A 3500 says with no punto
- **THEN** the body is an ordered extract of at most `CONTEXT_CHUNK_CHARS` characters, not the full texto ordenado

### Requirement: Vigente prefers current law plus later patches
When the user question uses a vigente intent from the closed list as whole words or phrases (hoy, vigente, puedo, qué exige, que exige, liquidar, today, current, liquidate) and does not name a Comunicación A number, the system SHALL search the texto ordenado first and SHALL also consider Comunicaciones A issued after the Comunicación recorded in `to_as_of` (that id’s issue date, or a later A number). It MUST NOT compare an issue date to the `to_as_of` id as if they were the same kind of value. It MUST NOT answer a vigente question using only a superseded 1980s or 2002 document when a TO or post-TO clause exists.

#### Scenario: Export proceeds today
- **GIVEN** the TO as of A 8307 and later Adecuaciones after 2025-08-25
- **WHEN** the user asks “qué se exige hoy para liquidar el cobro de exportaciones”
- **THEN** a citation has doc kind texto ordenado or a fecha after 2025-08-25
- **AND** the answer does not cite only a 2002 comunicación

#### Scenario: Patch after TO (tipo de cambio de referencia)
- **GIVEN** A 3500 (2002) and A 8359 (after TO freeze) are both in the dump
- **WHEN** the user asks for the current tipo de cambio de referencia rule as vigente
- **THEN** retrieval includes A 8359 or the TO as applicable
- **AND** does not present A 3500 alone as the current rule

### Requirement: Aliases
The system SHALL expand a small alias list before retrieval (including vigente search). The list MUST map MULC to “Mercado Único y Libre de Cambios”, cepo to “restricciones cambiarias”, and keep “tipo de cambio de referencia” as a retrieval phrase. Comunicación numbers are named lookup, not aliases.

#### Scenario: MULC alias
- **GIVEN** aliases include MULC → Mercado Único y Libre de Cambios
- **WHEN** the user asks about the MULC
- **THEN** retrieval also uses “Mercado Único y Libre de Cambios”

### Requirement: Cross-reference one hop
If a retrieved clause cross-references another Comunicación A (including “véase Com. A”, “ver Comunicación A”, or “según Com. A”), the system SHALL fetch that id only if it is in the dump, at most one extra fetch per turn. The system SHALL NOT invent the missing text. Finding SHALL be silencio for a missing target only when the asked-for rule is not already in the retrieved clauses (the user question depends on that missing target). An incidental cross-reference MUST NOT wipe an otherwise sufficient answer.

#### Scenario: Xref target is fetched
- **GIVEN** a clause that cites Com. A 3500
- **AND** A 3500 is in the manifest
- **WHEN** the user question depends on that xref
- **THEN** the system fetches A 3500 once
- **AND** does not follow a second xref hop in the same turn

#### Scenario: Missing xref is silencio when dependent
- **GIVEN** a clause that cites Com. A 7777
- **AND** A 7777 is not in the manifest
- **AND** the asked-for rule is not in the already-retrieved clauses
- **WHEN** the user question depends on that xref
- **THEN** finding is silencio
- **AND** the system does not fabricate A 7777’s text

#### Scenario: Incidental missing xref does not force silencio
- **GIVEN** a texto ordenado clause that already answers the question
- **AND** that clause also says “véase Com. A 7777”
- **AND** A 7777 is not in the manifest
- **WHEN** the user asks a vigente rule question that the TO clause answers
- **THEN** finding is not silencio solely because of that missing xref
- **AND** the system does not fabricate A 7777’s text

### Requirement: Stable chunk identifiers
Chunk identifiers SHALL be stable across refresh when the source checksum is unchanged, so L1 gold citations remain valid.

#### Scenario: Refresh does not rename unchanged chunks
- **GIVEN** a chunk id for TO punto 3.8.5
- **WHEN** refresh runs and the TO checksum is unchanged
- **THEN** that chunk id is still the same

### Requirement: Named sections are ordered and punto-scoped
A fetched named section SHALL assemble that document's chunks in document order: by the `ordinal` recorded at ingest when every chunk has one, otherwise by numeric punto then ingest order. When the question names a punto, the section SHALL contain that punto and its sub-puntos plus one neighbouring chunk on each side; when the punto is not found, the whole ordered document is used. The section SHALL be capped at `CONTEXT_CHUNK_CHARS`. Ingest SHALL record an `ordinal` on every chunk.

#### Scenario: Punto with sub-puntos and neighbours
- **GIVEN** `A3500` has chunks with puntos 1, 2, 2.1, 2.2, 3, 4 in that order
- **WHEN** the user asks about punto 2 of A 3500
- **THEN** the fetched section contains puntos 1, 2, 2.1, 2.2 and 3, in that order
- **AND** it does not contain punto 4

#### Scenario: Whole document in order when punto is missing
- **GIVEN** `A3500` has chunks with puntos 1, 2, 3 stored out of order
- **WHEN** the user asks about punto 9.9.9 of A 3500
- **THEN** the fetched section is puntos 1, 2, 3 in that order

#### Scenario: Ingest records ordinals
- **GIVEN** a document is ingested
- **WHEN** its chunks are stored
- **THEN** each chunk has an integer `ordinal` starting at 0 in document order

### Requirement: Hybrid lexical and dense search
Similarity search over the index SHALL combine a dense embedding query with a lexical BM25 query over the same chunks using reciprocal-rank fusion, and SHALL return the top k fused chunks. A chunk that matches the query only lexically (for example by an exact Comunicación number or punto token) SHALL be reachable. Each returned chunk SHALL carry a fused `score` in (0, 1], its `dense_score` (0 when it was not a dense hit) and its lexical rank. The lexical index SHALL be built from the collection once per collection version (chunk count and dump manifest version) and MUST NOT be rebuilt per query. The operator MAY disable fusion (`RETRIEVAL_HYBRID=false`), in which case results are dense-only as before. The number of candidates taken from each side is configurable (`RETRIEVAL_CANDIDATES`, default 20).

#### Scenario: Exact token reachable through the lexical side
- **GIVEN** a chunk whose text contains "SECOEXPO" and whose embedding is far from the query embedding
- **WHEN** the user asks about SECOEXPO
- **THEN** that chunk is among the returned hits

#### Scenario: Hybrid off equals dense-only
- **GIVEN** `RETRIEVAL_HYBRID=false`
- **WHEN** a query runs
- **THEN** the hits and their scores equal the dense-only ranking

### Requirement: Similarity floor for silencio
When `RETRIEVAL_MIN_SCORE` is greater than 0 and the collection uses cosine space, similarity search SHALL return no hits when the best dense cosine similarity is below that floor, so the router answers silencio with reason `empty_hits` without calling the language model. When the collection does not use cosine space, the floor SHALL be ignored with a logged warning. The default is 0 (off).

#### Scenario: Unrelated question below the floor
- **GIVEN** `RETRIEVAL_MIN_SCORE=0.3` on a cosine collection
- **AND** the best cosine similarity for the question is 0.1
- **WHEN** the user asks that question
- **THEN** finding is silencio with reason `empty_hits`
- **AND** the language model is not called

### Requirement: Cosine space for new collections
A collection created by ingest SHALL use the configured `INDEX_SPACE` (default `cosine`). An existing collection keeps its space; switching space requires removing the index and re-ingesting, and the operator documentation SHALL say so.

#### Scenario: Fresh index is cosine
- **GIVEN** no index directory
- **WHEN** ingest creates the collection with default settings
- **THEN** the collection metadata records cosine space
