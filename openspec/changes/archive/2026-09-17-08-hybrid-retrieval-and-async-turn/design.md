## Context

See proposal.md Why. Five ports stay five; `IndexPort.search(query, *, k, filters) -> list[Chunk]` unchanged.

Facts as of this change's writing:
- `ChromaIndex._get_collection` (`index_chroma.py:39-61`): `client.get_or_create_collection(name=COLLECTION, embedding_function=ef)` — no `metadata`, so the space is Chroma's default (`l2`). `search` (`:87-147`): `n_results = k` (×3 with filters), `collection.query(query_texts=[query], n_results, include=[documents, metadatas, distances], where?)`, `metadata_matches` post-filter, `score = 1/(1+distance)`, stops at `k`.
- `FakeIndex.search` (`index_fake.py:28-80`) has an inline Spanish/English stoplist and term scoring.
- `dump_health(settings, index)` (`domain/health.py`): `Manifest.load` + `index.has_document(TO_DOC_ID)` (or any). `Manifest.load(path)` (`domain/manifest.py:24-41`) parses JSON each call.
- `_respond`: `health = dump_health(...)` (`answer_query.py:138`), `manifest = Manifest.load(self._settings.manifest_path)` (`:255`), `Router(self._index, manifest).route(...)` (`:259`) — all synchronous inside the coroutine.
- Router silencio when `not routed.hits` → reason `empty_hits` (`answer_query.py:275`).
- `DeterministicEmbeddingFunction` (`adapters/embeddings.py`) makes Chroma tests hermetic (`tests/test_index.py`).
- `tests/test_answer_query.py::test_index_not_ready_no_llm` (`:387-399`) constructs `AnswerQuery` with an empty `FakeIndex` and expects `index_not_ready` on the first call.

## Goals / Non-Goals

**Goals:** exact-token recall; a principled silencio floor available to operators; no event-loop blocking per turn.
**Non-Goals:** reranking; changing the router's routes; changing chunking.

## Decisions

### Decision: In-package BM25 and RRF (domain, no dependency)

`src/bcra_rag/domain/text.py`: `SPANISH_STOPWORDS: frozenset[str]` (the set currently inlined in `FakeIndex.search`), `tokenize(text) -> list[str]` (NFKD → strip combining marks → lowercase → `re.findall(r"[a-z0-9]+")` → drop stopwords and tokens shorter than 2, but keep pure digits so "3500", "8.4.1" → "8","4","1" survive; also emit joined forms for `a 3500` → `a3500` by a second pass over `re.findall(r"\ba\s?(\d{2,5})\b", lower)`).
`src/bcra_rag/domain/bm25.py`:
```python
@dataclass
class Bm25Index:
    k1: float = 1.5
    b: float = 0.75
    # built fields: doc_len, avg_len, df, postings: dict[str, list[tuple[int, int]]], ids: list[str]
    @classmethod
    def build(cls, docs: Sequence[tuple[str, str]]) -> "Bm25Index": ...
    def search(self, query: str, n: int) -> list[tuple[str, float]]: ...   # (chunk_id, score) desc

def rrf(rankings: Sequence[Sequence[str]], *, k: int = 60) -> list[tuple[str, float]]: ...
```
Standard BM25 (IDF `ln((N - df + 0.5)/(df + 0.5) + 1)`); `rrf` sums `1/(k + rank)` per id over the rankings and sorts descending, stable on first appearance.

### Decision: Hybrid inside the Chroma adapter with a lexicon cache

Settings:
```python
retrieval_hybrid: bool = True
retrieval_candidates: int = Field(default=20, ge=5, le=100)
retrieval_min_score: float = Field(default=0.0, ge=0.0, le=1.0)
index_space: Literal["cosine", "l2", "ip"] = "cosine"
```
`_get_collection` passes `metadata={"hnsw:space": self._settings.index_space}` to `get_or_create_collection` (Chroma applies it on creation only; an existing collection keeps its stored space and `collection.metadata` reports it).

`search`:
1. `count = collection.count()`; `n = min(max(k, 1) * (3 if filters else 1), count)` as today, but when hybrid `n_dense = min(max(self._settings.retrieval_candidates, k), count)`.
2. Dense: `collection.query(...)` as today → list of `(chunk_id, text, metadata, distance)` in rank order (filtered with `metadata_matches`).
3. Lexical (hybrid only): `lex = self._lexicon()` — cached `Bm25Index` built from `collection.get(include=["documents", "metadatas"])` (all chunks; ~thousands), keyed by `(collection.count(), manifest_mtime_ns)` where `manifest_mtime_ns = self._settings.manifest_path.stat().st_mtime_ns` if the file exists else 0; rebuilt when the key changes. `lex.search(query, n_dense)` → ids; texts/metadata for lexical-only ids come from the same cached `get` payload (store `self._lexicon_rows: dict[chunk_id, (text, metadata)]`); apply `metadata_matches`.
4. Fuse: `fused = rrf([dense_ids, lexical_ids])`; take the first `k`; build `Chunk(chunk_id, text, {**metadata, "score": fused_score / fused[0][1], "dense_score": 1/(1+distance) if seen in dense else 0.0, "lexical_rank": r or -1})`.
5. Floor: when `self._settings.retrieval_min_score > 0` and the collection space is cosine (`(collection.metadata or {}).get("hnsw:space") == "cosine"`): `best_sim = 1 - min(distance over dense hits)`; if `best_sim < retrieval_min_score` → log `retrieval_below_floor` and return `[]`. When the space is not cosine and the floor is set, log a one-time warning `retrieval_floor_ignored_space` and skip the floor.
6. `retrieval_hybrid=False` → exactly today's path (dense only, score `1/(1+distance)`).

`FakeIndex.search` imports `SPANISH_STOPWORDS`/`tokenize` from `domain/text.py` instead of its inline set (behaviour unchanged).

### Decision: Cached manifest and health; retrieval off the loop

`Manifest.load_cached(path)`: module-level `dict[Path, tuple[tuple[int, int], Manifest]]`; key `(st_mtime_ns, st_size)`; returns the cached instance when the key matches (missing file → key `(0, 0)` and an empty manifest, also cached). `dump_health` uses `Manifest.load_cached` and caches the `HealthResponse` in a module dict keyed by `(str(path), key, id(index))`; `has_document` is therefore called once per manifest version. `_respond`: `health = await asyncio.to_thread(dump_health, self._settings, self._index)`; `manifest = Manifest.load_cached(...)`; `routed = await asyncio.to_thread(Router(self._index, manifest).route, query, k=k, to_as_of=...)` (keep the surrounding `retrieve` span enter/exit and the `retrieve_ms` timing from change 04). `Router` and `ChromaIndex` are used from a worker thread: Chroma's embedded client is thread-safe for reads; the lexicon cache build is guarded by a `threading.Lock`.

`test_index_not_ready_no_llm` keeps passing because the empty `FakeIndex` state exists before the first call; add a test that a manifest rewrite (new mtime/size) invalidates the health cache.

## Risks / Trade-offs

- [Lexicon memory] → all chunk texts of the corpus (~973 docs) in RAM once; escape hatch `RETRIEVAL_HYBRID=false`.
- [RRF changes the top-5 for dense-only-happy queries] → L1 rerun is the check; `retrieval_hybrid` is a setting so a regression can be reverted without code.
- [Same-second manifest rewrite with equal size] → key also includes mtime_ns (nanosecond), practically unique.

## Migration Plan

Deploy; to switch an existing index to cosine: stop the service, remove `data/index`, `uv run python -m bcra_rag.jobs.ingest`, start. Rerun L1.

## Open Questions

None.
