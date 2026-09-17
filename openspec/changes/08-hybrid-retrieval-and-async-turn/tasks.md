# Tasks — 08 hybrid retrieval and async turn

Requires changes 01 and 04 (`retrieve_ms` timing site). Line anchors are as of this change's writing; grep the quoted symbol if they moved. Chroma tests use `DeterministicEmbeddingFunction` from `bcra_rag.adapters.embeddings` (see `tests/test_index.py:109-135`).

## 1. domain — tokenizer, BM25, RRF

- [ ] 1.1 Create `src/bcra_rag/domain/text.py` with `SPANISH_STOPWORDS` (move the literal set from `src/bcra_rag/adapters/index_fake.py::search`, ~line 37-62) and
  ```python
  def tokenize(text: str) -> list[str]:
      lowered = unicodedata.normalize("NFKD", text or "").lower()
      lowered = "".join(ch for ch in lowered if not unicodedata.combining(ch))
      tokens = [t for t in re.findall(r"[a-z0-9]+", lowered) if len(t) >= 2 and t not in SPANISH_STOPWORDS]
      tokens += [f"a{num}" for num in re.findall(r"\ba\s?(\d{2,5})\b", lowered)]
      return tokens
  ```
  Update `FakeIndex.search` to use `tokenize`/`SPANISH_STOPWORDS` (keep its scoring); run `uv run pytest tests/test_index.py tests/test_router.py -q` → passes.
- [ ] 1.2 Create `src/bcra_rag/domain/bm25.py` with `Bm25Index.build(docs: Sequence[tuple[str, str]])`, `Bm25Index.search(query: str, n: int) -> list[tuple[str, float]]` (standard BM25, `k1=1.5`, `b=0.75`, IDF `math.log((N - df + 0.5) / (df + 0.5) + 1)`) and `rrf(rankings: Sequence[Sequence[str]], *, k: int = 60) -> list[tuple[str, float]]`.
- [ ] 1.3 Tests `tests/test_bm25.py`: `tokenize("Comunicación A 3500 punto 8.4.1")` contains `"a3500"`, `"3500"`, `"punto"`, not `"de"`; BM25 on three docs ranks the doc containing a rare query term first; a query with no matching term returns `[]`; `rrf([["a", "b"], ["b", "c"]])` puts `"b"` first; ties keep first-appearance order. Verify: `uv run pytest tests/test_bm25.py -q` → passes.

## 2. retrieval — settings and Chroma adapter

- [ ] 2.1 `src/bcra_rag/settings.py`, in the `# Retrieval` block: add
  ```python
  retrieval_hybrid: bool = True
  retrieval_candidates: int = Field(default=20, ge=5, le=100)
  retrieval_min_score: float = Field(default=0.0, ge=0.0, le=1.0)
  index_space: Literal["cosine", "l2", "ip"] = "cosine"
  ```
  (`from typing import Literal`). `tests/test_settings.py`: defaults + env parsing (`RETRIEVAL_HYBRID=false`, `INDEX_SPACE=l2`).
- [ ] 2.2 `src/bcra_rag/adapters/index_chroma.py`:
  - `_get_collection`: `get_or_create_collection(name=COLLECTION, embedding_function=ef, metadata={"hnsw:space": self._settings.index_space})`.
  - Add `self._lexicon_key: tuple[int, int] | None = None`, `self._lexicon: Bm25Index | None = None`, `self._lexicon_rows: dict[str, tuple[str, dict[str, Any]]] = {}`, `self._lock = threading.Lock()`, `self._floor_warned = False` in `__init__`.
  - Add `_manifest_mtime_ns()` (0 when the manifest is missing) and `_lexicon(collection)` implementing the cache described in design.md (`collection.get(include=["documents", "metadatas"])`, build `Bm25Index` over `(chunk_id, text)`, store rows).
  - Rewrite `search` per design.md steps 1-6; keep the existing `chroma_query_failed` retry; when `retrieval_hybrid` is false keep the current behaviour byte-for-byte (score `1/(1+distance)`).
  - Floor: compute `best_sim = 1.0 - min(distances)` only when `(collection.metadata or {}).get("hnsw:space") == "cosine"`.
- [ ] 2.3 Tests `tests/test_index.py`:
  ```python
  def test_chroma_hybrid_finds_lexical_only_term(tmp_path) -> None:
      settings = Settings(data_dir=tmp_path)
      index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())
      index.upsert("A1", [Chunk("A1:0", "el sistema SECOEXPO recibe la documentación", {"doc_kind": "comunicacion"})])
      index.upsert("A2", [Chunk("A2:0", "tipo de cambio de referencia promedio ponderado", {"doc_kind": "comunicacion"})])
      hits = index.search("SECOEXPO", k=1)
      assert hits and hits[0].metadata["doc_id"] == "A1"
      assert 0.0 < float(hits[0].metadata["score"]) <= 1.0


  def test_chroma_hybrid_off_is_dense_only(tmp_path) -> None:
      settings = Settings(data_dir=tmp_path, retrieval_hybrid=False)
      index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())
      index.upsert("A1", [Chunk("A1:0", "texto uno", {"doc_kind": "comunicacion"})])
      hits = index.search("texto uno", k=1)
      assert "lexical_rank" not in hits[0].metadata


  def test_chroma_floor_returns_empty_on_cosine(tmp_path) -> None:
      settings = Settings(data_dir=tmp_path, retrieval_min_score=0.99)
      index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())
      index.upsert("A1", [Chunk("A1:0", "texto uno", {"doc_kind": "comunicacion"})])
      assert index.search("algo totalmente distinto", k=1) == []


  def test_chroma_new_collection_is_cosine(tmp_path) -> None:
      index = ChromaIndex(Settings(data_dir=tmp_path), embedding_function=DeterministicEmbeddingFunction())
      assert (index._get_collection().metadata or {}).get("hnsw:space") == "cosine"
  ```
  (`DeterministicEmbeddingFunction` must produce different vectors for different texts; if the floor test cannot be made to fail deterministically, assert instead with `retrieval_min_score=1.0` and a query differing from every chunk.) Also keep `test_chroma_search_and_fecha_filter` and `test_chroma_search_retries_after_value_error` green (filters still apply after fusion). Verify: `uv run pytest tests/test_index.py -q` → passes.

## 3. platform — cached manifest/health, retrieval off the loop

- [ ] 3.1 `src/bcra_rag/domain/manifest.py`: add
  ```python
  _CACHE: dict[Path, tuple[tuple[int, int], "Manifest"]] = {}

  @classmethod
  def load_cached(cls, path: Path) -> Manifest:
      try:
          stat = path.stat()
          key = (stat.st_mtime_ns, stat.st_size)
      except OSError:
          key = (0, 0)
      cached = _CACHE.get(path)
      if cached is not None and cached[0] == key:
          return cached[1]
      loaded = cls.load(path)
      _CACHE[path] = (key, loaded)
      return loaded
  ```
  (module-level dict; `Manifest` dataclass must not be mutated by callers — `Router` only reads it; ingest uses `load`, not `load_cached`).
- [ ] 3.2 `src/bcra_rag/domain/health.py`: `dump_health` uses `Manifest.load_cached`; cache the `HealthResponse` in a module dict keyed by `(str(settings.manifest_path), manifest_key, id(index))` where `manifest_key` is the same `(mtime_ns, size)`; expose `clear_health_cache()` for tests.
- [ ] 3.3 `src/bcra_rag/use_cases/answer_query.py::_respond`: `health = await asyncio.to_thread(dump_health, self._settings, self._index)`; `manifest = Manifest.load_cached(self._settings.manifest_path)`; `routed = await asyncio.to_thread(Router(self._index, manifest).route, query, k=k, to_as_of=manifest.to_as_of or to_as_of)` inside the existing `try` with the span exit and `retrieve_ms` timing preserved.
- [ ] 3.4 Tests: `tests/test_health.py` add `test_health_cache_invalidates_on_manifest_rewrite` (write manifest with `last_refresh` A, call `dump_health`, rewrite with B and a different size or wait for a new mtime — write extra whitespace to change the size — call again → B). `tests/test_answer_query.py`: `test_index_not_ready_no_llm` (~line 387) unchanged and green; add `test_retrieval_runs_in_worker_thread` using a `FakeIndex` subclass whose `search` records `threading.get_ident()` and asserting it differs from the test's loop thread id. Verify: `uv run pytest tests/test_health.py tests/test_answer_query.py tests/test_chat_api.py -q` → passes.

## 4. Docs, spec sync, gates

- [ ] 4.1 README Ingest section: "`INDEX_SPACE` (cosine) applies to a new collection only; to switch an existing index stop the service, delete `data/index`, re-ingest." Debug section: `RETRIEVAL_HYBRID` (true), `RETRIEVAL_CANDIDATES` (20), `RETRIEVAL_MIN_SCORE` (0 = off; cosine collections only). `.env.example` / `deploy/env.remote.example`: commented lines for the four settings. Evals section: rerun L1 after enabling hybrid.
- [ ] 4.2 Sync deltas into `openspec/specs/{retrieval,platform}/spec.md`.
- [ ] 4.3 `uv run ruff check .`; `uv run mypy src`; `uv run pytest -q --cov=src --cov-report=term-missing` → green, ≥ 80%.
- [ ] 4.4 Operator check: ask "Qué dice el punto 8.4.1 del texto ordenado?" and confirm the retrieve chip detail/log shows a lexical hit; with `RETRIEVAL_MIN_SCORE=0.3` on a re-ingested cosine index, "What's the weather in Madrid?" is blocked by scope before retrieval (unchanged) and a nonsense CAMEX-worded question ("swap de cebollas cambiarias") returns silencio `empty_hits` without an LLM call.
