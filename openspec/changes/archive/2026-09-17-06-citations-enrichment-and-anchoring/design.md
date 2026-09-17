## Context

See proposal.md Why. Five ports stay five; `IndexPort.get_section(doc_id, punto)` keeps its signature.

Facts as of this change's writing:
- `Citation` (`schemas.py:18-26`): `id, tipo, fecha, punto, snippet, url`. `citation_cards` (`ui/config.py:342-355`) copies `fecha`, `punto`, `url`; `citation_card_markdown` (`:326-339`) prints `fecha —` when missing.
- `_citations_from_model` (`answer_query.py:775-792`) copies only `snippet`/`tipo`; `_cite_failures` (`:717-732`) reasons `unknown_id | empty_snippet | quote_not_in_hit`; `_salvage_named` (`:743-771`) replaces a paraphrased snippet on the named route with `hit.text[:280]`.
- `generate_from_context` (`:433`) does not know the manifest; `_respond` loads it at `:255`. `run_generation.py:47-53` (evals) also calls `generate_from_context`.
- `CiteOrAbstainRail.run` (`output.py:37-77`) uses `_quote_ok(citation, hits)` (`:220-231`) → `_norm_span` (`:234-238`: collapse whitespace, space after punctuation, lowercase, strip `.;:,`).
- Manifest documents: `{sha256, kind, url, indexed, title?, fecha?}` (`domain/manifest.py:17-22`); chunk metadata at ingest: `doc_kind, numero, title, fecha` (+ `punto`, `doc_part`, `chunker` from `StructuredChunker`, `domain/chunkers.py:110-123`); no ordinal. `ChromaIndex.upsert` adds `doc_id`.
- `ChromaIndex.get_section` (`index_chroma.py:149-160`): `collection.get(where={"$and": [{"doc_id": …}, {"punto": …}]})`, else whole doc; `"\n".join(docs)[:2000]`. `FakeIndex.get_section` (`index_fake.py:87-94`) returns the first punto chunk `[:2000]` or the join.
- Router `_named_fetch` (`router.py:84-104`) → `_chunk_from_section(doc_id, text, manifest)` (`:213-226`) builds `Chunk(f"{doc_id}:section", text, {doc_id, doc_kind, numero, fecha, score})`.
- `_prompt` clips `chunk.text[:1500]` (`answer_query.py:670`).
- Spec `query-answering` "Named-fetch snippet salvage" (`:258-`) and `guardrails` "Cite or abstain" (`:25-53`): "Retrieved hits MUST NOT be copied in as citations to satisfy this rule."

## Goals / Non-Goals

**Goals:** cards with date and link; fewer false silencios on near-verbatim quotes without loosening the this-turn-id rule; complete, ordered named sections.
**Non-Goals:** fuzzy matching across documents; changing the salvage contract; re-ranking.

## Decisions

### Decision: Enrich after validation, from the dump only

```python
def enrich_citations(
    citations: list[Citation], hits: list[Chunk], doc_meta: Mapping[str, Mapping[str, Any]]
) -> list[Citation]:
    by_doc = {str(c.metadata.get("doc_id") or ""): c for c in hits if c.metadata.get("doc_id")}
    out: list[Citation] = []
    for item in citations:
        entry = doc_meta.get(item.id) or {}
        chunk = by_doc.get(item.id)
        update: dict[str, Any] = {}
        fecha = entry.get("fecha") or (chunk.metadata.get("fecha") if chunk else None)
        url = entry.get("url") or (TO_PDF_URL if item.id == TO_DOC_ID else None)
        if fecha and not item.fecha:
            update["fecha"] = str(fecha)
        if url and not item.url:
            update["url"] = str(url)
        if not item.punto and chunk is not None and chunk.metadata.get("punto"):
            update["punto"] = str(chunk.metadata["punto"])
        out.append(item.model_copy(update=update) if update else item)
    return out
```
Called in `generate_from_context` right after `_citations_from_model` (before `_salvage_named`), with `doc_meta` = `manifest.documents` passed by `_respond`; `generate_from_context(..., doc_meta: Mapping[str, Mapping[str, Any]] | None = None)` defaults to `{}` (evals path). `_chunk_from_section` adds `"url": entry.get("url") or ""`, `"title": entry.get("title") or ""`, and `"punto": punto or ""` (the router passes the parsed punto). The system prompt (change 05) describes `citations` objects as `{id, tipo, punto, snippet}` — no change needed; `_citation` in the adapter keeps accepting `fecha`/`url` if a model sends them.

### Decision: Anchored quotes

In `output.py`:
```python
MIN_ANCHOR_CHARS = 40
MIN_ANCHOR_RATIO = 0.6

def anchor_span(citation: Citation, hits: list[Chunk]) -> tuple[str, bool] | None:
    """Return (verbatim_span, adjusted). None when the snippet has no usable anchor."""
    quote = _norm_span(citation.snippet or "")
    if not quote:
        return None
    for chunk in hits:
        if str(chunk.metadata.get("doc_id") or "") != citation.id:
            continue
        body = _norm_span(chunk.text)
        if quote in body:
            return citation.snippet, False
        run = _longest_common_run(quote, body)      # longest word-window of `quote` found in `body`
        if run and (len(run) >= MIN_ANCHOR_CHARS or len(run) >= MIN_ANCHOR_RATIO * len(quote)):
            original = _recover_original(run, chunk.text)  # regex of the run's words joined by \W+, case-insensitive
            if original:
                return original, True
    return None
```
`_longest_common_run`: split `quote` into words; for window sizes from `len(words)` down to 3, slide over the words and return the first window whose `" ".join` is in `body`. O(n²) on ≤ ~60-word snippets — fine. `_recover_original(run, text)`: `re.search(r"\W+".join(map(re.escape, run.split())), text, re.IGNORECASE)` → `match.group(0)`.

`CiteOrAbstainRail.run`: for each allowed citation call `anchor_span`; collect `valid` with replaced snippets and count `adjusted`; verdict `warn` with detail `f"cita ajustada ({adjusted})"` when `adjusted > 0`, else `pass` as today; `block` unchanged when `valid` is empty. `_quote_ok(citation, hits)` becomes `anchor_span(citation, hits) is not None` (used by `_cite_failures` and `_salvage_named`), and `_cite_failures` adds reason `quote_adjusted` when `anchor_span(...)[1]` is true (log only). The rail's patch only rewrites the snippet of a citation the model produced with this-turn id, so "retrieved hits MUST NOT be copied in" still holds.

### Decision: Ordered sections in the domain

New `src/bcra_rag/domain/sections.py`:
```python
def punto_key(value: str | None) -> tuple[int, ...]: ...   # "3.8.5" -> (3, 8, 5); non-numeric parts -> large sentinel; None -> ()
def order_chunks(chunks: Sequence[Chunk]) -> list[Chunk]:
    # sort by metadata["ordinal"] when present on all chunks, else by punto_key then insertion order
def section_text(chunks: Sequence[Chunk], punto: str | None, max_chars: int) -> str:
    # ordered = order_chunks(chunks)
    # if punto: pick = chunks whose punto == punto or startswith punto + "."; if pick: extend with one neighbour before and after in `ordered`
    # else pick = ordered
    # return "\n".join(c.text for c in pick)[:max_chars]
```
`ChromaIndex.get_section` fetches all chunks of `doc_id` once (`collection.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])`), rebuilds `Chunk` objects, and returns `section_text(chunks, punto, self._settings.context_chunk_chars)`. `FakeIndex.get_section` does the same over `self.docs[doc_id]`. Ingest: `IngestCorpus._chunk` sets `chunk.metadata["ordinal"] = i` for `i, chunk in enumerate(chunks)` after chunking. Settings: `context_chunk_chars: int = Field(default=3000, ge=500)`; `_prompt(..., chunk_chars: int)` clips `chunk.text[:chunk_chars]`, `generate_from_context` gains `chunk_chars: int = 1500` and `_respond` passes `self._settings.context_chunk_chars`.

## Risks / Trade-offs

- [Anchor accepts a 40-char run from a different sentence] → the run is verbatim text from the cited document with the same id; the card shows the real span, which is stricter than today's salvage (`text[:280]`).
- [Bigger sections raise prompt tokens] → bounded by `CONTEXT_CHUNK_CHARS` and `MAX_CONTEXT_CHARS` (context-budget rail).
- [Existing indexes without `ordinal`] → punto fallback; unstructured (chunker A) docs keep insertion order, which Chroma does not guarantee — acceptable until re-ingest (documented).

## Migration Plan

Deploy; optionally re-ingest (`uv run python -m bcra_rag.jobs.ingest`) to add ordinals. Rerun L1 afterwards.

## Open Questions

None.
