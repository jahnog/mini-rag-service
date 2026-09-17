## ADDED Requirements

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
