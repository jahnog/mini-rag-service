# Tasks — 06 citations enrichment and anchoring

Requires changes 01, 04, 05. Line anchors are as of this change's writing; grep the quoted symbol if they moved. The existing tests `test_named_a3500_paraphrased_snippet_is_salvaged` (English paraphrase → salvage) and `test_similar_paraphrased_snippet_is_silencio` (English paraphrase on the similar route → silencio) must keep passing: an English paraphrase shares no 3-word run with the Spanish text, so the anchor does not fire.

## 1. retrieval — ordered sections

- [ ] 1.1 Create `src/bcra_rag/domain/sections.py`:
  ```python
  from __future__ import annotations

  from collections.abc import Sequence

  from bcra_rag.domain.models import Chunk

  _BIG = 10**6


  def punto_key(value: str | None) -> tuple[int, ...]:
      if not value:
          return ()
      parts: list[int] = []
      for piece in str(value).split("."):
          parts.append(int(piece) if piece.isdigit() else _BIG)
      return tuple(parts)


  def order_chunks(chunks: Sequence[Chunk]) -> list[Chunk]:
      items = list(chunks)
      if items and all(isinstance(c.metadata.get("ordinal"), int) for c in items):
          return sorted(items, key=lambda c: int(c.metadata["ordinal"]))
      indexed = list(enumerate(items))
      indexed.sort(key=lambda pair: (punto_key(str(pair[1].metadata.get("punto") or "") or None), pair[0]))
      return [c for _, c in indexed]


  def section_text(chunks: Sequence[Chunk], punto: str | None, max_chars: int) -> str:
      ordered = order_chunks(chunks)
      pick = ordered
      if punto:
          wanted = [i for i, c in enumerate(ordered) if _matches(str(c.metadata.get("punto") or ""), punto)]
          if wanted:
              lo = max(0, wanted[0] - 1)
              hi = min(len(ordered), wanted[-1] + 2)
              pick = ordered[lo:hi]
      return "\n".join(c.text for c in pick)[:max_chars]


  def _matches(chunk_punto: str, punto: str) -> bool:
      return chunk_punto == punto or chunk_punto.startswith(punto + ".")
  ```
- [ ] 1.2 `src/bcra_rag/settings.py`: after `max_context_chars` add `context_chunk_chars: int = Field(default=3000, ge=500)`.
- [ ] 1.3 `src/bcra_rag/adapters/index_chroma.py::get_section` (~line 149-160): replace the body with one `collection.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])`, rebuild `chunks = [Chunk(str(i), str(d), dict(m or {})) for i, d, m in zip(got.get("ids") or [], got.get("documents") or [], got.get("metadatas") or [], strict=False)]`, and `return section_text(chunks, punto, self._settings.context_chunk_chars)`. `src/bcra_rag/adapters/index_fake.py::get_section` (~line 87-94): `return section_text(self.docs.get(doc_id, []), punto, 3000)` (FakeIndex has no settings; keep 3000 literal or accept a constructor kwarg `context_chunk_chars=3000`).
- [ ] 1.4 Ingest ordinal: in `src/bcra_rag/use_cases/ingest_corpus.py::_chunk` (~line 313-319) replace `return chunker.chunk(doc_id, text, metadata)` with
  ```python
  chunks = chunker.chunk(doc_id, text, metadata)
  for i, chunk in enumerate(chunks):
      chunk.metadata["ordinal"] = i
  return chunks
  ```
  (`Chunk.metadata` is a plain mutable dict, `domain/models.py:19-22`).
- [ ] 1.5 `src/bcra_rag/domain/router.py`: `_named_fetch` passes `punto` to `_chunk_from_section(comm_id, text, self._manifest, punto)`; `_chunk_from_section` (~line 213-226) gains `punto: str | None = None` and adds to metadata `"url": entry.get("url") or ""`, `"title": entry.get("title") or ""`, `"punto": punto or ""`.
- [ ] 1.6 Tests: new `tests/test_sections.py` covering `punto_key("3.8.5") == (3, 8, 5)`, `order_chunks` by ordinal, by punto fallback (chunks given as 3,1,2 → 1,2,3), `section_text` punto 2 with 1, 2, 2.1, 2.2, 3, 4 → contains "1", "2", "2.1", "2.2", "3" texts in order and not "4"; missing punto → whole ordered doc; cap respected. `tests/test_index.py::test_chroma_get_section_falls_back_when_punto_missing` (~line 182) stays green; add `test_chroma_get_section_orders_by_punto` upserting three chunks with puntos "3","1","2" (texts "tres","uno","dos") and asserting `get_section("A1").split("\n") == ["uno", "dos", "tres"]`. `tests/test_ingest.py`: assert `index.docs["A100"][0].metadata["ordinal"] == 0` next to the existing `doc_kind` assertion (~line 135). `tests/test_router.py` (or wherever `_chunk_from_section` is tested): assert `url`/`punto` metadata present. Verify: `uv run pytest tests/test_sections.py tests/test_index.py tests/test_ingest.py tests/test_router.py -q` → passes.

## 2. query-answering — chunk cap and enrichment

- [ ] 2.1 `src/bcra_rag/use_cases/answer_query.py::_prompt` (~line 661): add parameter `chunk_chars: int` and use `chunk.text[:chunk_chars]` (~line 670). `generate_from_context` gains `chunk_chars: int = 1500` and `doc_meta: Mapping[str, Mapping[str, Any]] | None = None`; passes `chunk_chars` to `_prompt`. `_respond` passes `chunk_chars=self._settings.context_chunk_chars, doc_meta=manifest.documents`.
- [ ] 2.2 Add `enrich_citations` (design.md) to `answer_query.py` (imports `TO_DOC_ID, TO_PDF_URL` from `bcra_rag.domain.urls`) and call it right after `citations = _citations_from_model(...)` (~line 465): `citations = enrich_citations(citations, ctx.hits, doc_meta or {})`.
- [ ] 2.3 Tests `tests/test_answer_query.py`:
  ```python
  @pytest.mark.asyncio
  async def test_citations_are_enriched_from_manifest(tmp_path: Path) -> None:
      settings, index, _ = seed_ready(tmp_path)
      use_case = AnswerQuery(settings, index, FakeLlm(IN_CORPUS_DRAFT), InMemorySessionStore(), default_pipeline(settings))
      response = await use_case.run(ChatRequest(message="qué se exige hoy para liquidar el cobro de exportaciones"), request_id="e")
      cite = response.citations[0]
      assert cite.id == "texto_ordenado"
      assert cite.url == "https://www.bcra.gob.ar/Pdfs/Texord/t-excbio.pdf"
      assert cite.punto == "3.8.5"
  ```
  and a named-A variant asserting `fecha` equals the seeded manifest `fecha` for `A3500` (inspect `tests/chat_fixtures.py::seed_ready` for the seeded entry; if it has no `fecha`, add one there). `tests/test_ui.py`: extend the citation-card test so `citation_card_markdown({"id": "A8464", "fecha": "2026-08-06", "punto": "2", "snippet": "x", "url": "https://www.bcra.gob.ar/x.pdf"})` contains `fecha 2026-08-06` and the URL. Verify: `uv run pytest tests/test_answer_query.py tests/test_ui.py -q` → passes.

## 3. guardrails — anchored quotes

- [ ] 3.1 `src/bcra_rag/domain/guardrails/output.py`: add `MIN_ANCHOR_CHARS = 40`, `MIN_ANCHOR_RATIO = 0.6`, `anchor_span`, `_longest_common_run`, `_recover_original` as in design.md; rewrite `_quote_ok` as `return anchor_span(citation, hits) is not None`; in `CiteOrAbstainRail.run` (~line 47-58) build `valid` with the returned span (`citation.model_copy(update={"snippet": span})` when adjusted), count adjustments, return `verdict="warn", detail=f"cita ajustada ({adjusted})"` when `adjusted > 0`, otherwise the existing `pass`.
- [ ] 3.2 `answer_query.py::_cite_failures` (~line 717-732): before the `quote_not_in_hit` branch add `elif (span := anchor_span(item, hits)) is not None and span[1]: reason = "quote_adjusted"` (import `anchor_span`).
- [ ] 3.3 Tests `tests/test_guardrails.py` (next to ~line 647):
  ```python
  def test_cite_or_abstain_anchors_near_verbatim_quote() -> None:
      text = "Los residentes deberán liquidar el cobro de exportaciones en el mercado de cambios."
      ctx = _ctx("q", hits=[_hit("texto_ordenado", text)], finding=Finding.OBLIGACION,
                 citations=[Citation(id="texto_ordenado", tipo="TO",
                                     snippet="Los residentes deben liquidar el cobro de exportaciones en el mercado de cambios")])
      verdict = _run(CiteOrAbstainRail(), ctx)
      assert verdict.verdict == "warn"
      assert verdict.detail == "cita ajustada (1)"
      assert ctx.citations[0].snippet == "liquidar el cobro de exportaciones en el mercado de cambios"


  def test_cite_or_abstain_short_run_still_blocks() -> None:
      ctx = _ctx("q", hits=[_hit("texto_ordenado", "Los residentes deberán liquidar el cobro.")],
                 finding=Finding.OBLIGACION,
                 citations=[Citation(id="texto_ordenado", tipo="TO", snippet="Residents must settle export proceeds")])
      assert _run(CiteOrAbstainRail(), ctx).verdict == "block"
  ```
  (use the module's existing chunk helper name instead of `_hit` — check how `test_cite_or_abstain_valid_this_turn_quote_passes` builds hits and copy it.) Add a probe row `product.cite.anchored.warn` to `tests/fixtures/guardrail_probes.jsonl` modelled on the existing cite-or-abstain rows with `"expected": "warn"` (check `tests/test_guardrail_probes.py` for the accepted row shape; if it cannot express hits/citations, skip the probe and keep the unit test). Verify: `uv run pytest tests/test_guardrails.py tests/test_guardrail_probes.py tests/test_answer_query.py -q` → passes, including `test_similar_paraphrased_snippet_is_silencio` and `test_named_a3500_paraphrased_snippet_is_salvaged`.

## 4. Docs and spec sync

- [ ] 4.1 README: Debug/Ingest paragraph adds "`CONTEXT_CHUNK_CHARS` (3000) caps each prompt chunk and a fetched named section; re-ingest once to add chunk ordinals (existing indexes fall back to punto order)." `deploy/env.remote.example`, `.env.example`: `# CONTEXT_CHUNK_CHARS=3000`.
- [ ] 4.2 Sync deltas into `openspec/specs/{guardrails,query-answering,retrieval}/spec.md`.

## 5. Gates

- [ ] 5.1 `uv run ruff check .`; `uv run mypy src`; `uv run pytest -q --cov=src --cov-report=term-missing` → green, ≥ 80%.
- [ ] 5.2 Operator check: Staff view citation card shows `fecha <date>` and a `bcra.gob.ar` link; a near-verbatim quote shows a `warn cite-or-abstain` chip with "cita ajustada".
