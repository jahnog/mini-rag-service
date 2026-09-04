from bcra_rag.adapters.embeddings import DeterministicEmbeddingFunction
from bcra_rag.adapters.index_chroma import ChromaIndex
from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.domain.chunkers import StructuredChunker
from bcra_rag.domain.models import Chunk
from bcra_rag.settings import Settings


def test_fake_index_upsert_sets_chunker_and_events() -> None:
    index = FakeIndex()
    event = Chunk(
        "A100:evt",
        "Actualización del texto ordenado",
        {"doc_kind": "event", "chunker": "A"},
    )
    full = Chunk("A101:1", "Los residentes deberán", {"doc_kind": "comunicacion", "chunker": "B"})
    index.upsert("A100", [event])
    index.upsert("A101", [full])
    assert index.has_document("A100")
    assert index.docs["A100"][0].metadata["chunker"] == "A"
    assert "Actualización" in index.get_section("A100")


def test_to_replace_drops_old_punto() -> None:
    index = FakeIndex()
    index.upsert(
        "texto_ordenado",
        [
            Chunk("texto_ordenado:9.9", "solo en el TO viejo", {"punto": "9.9", "chunker": "B"}),
            Chunk("texto_ordenado:1", "permanece", {"punto": "1", "chunker": "B"}),
        ],
    )
    index.delete_document("texto_ordenado")
    index.upsert(
        "texto_ordenado",
        [Chunk("texto_ordenado:1", "permanece nuevo", {"punto": "1", "chunker": "B"})],
    )
    text = index.get_section("texto_ordenado")
    assert "solo en el TO viejo" not in text
    assert "permanece nuevo" in text


def test_missing_index_can_be_repaired_without_touching_other_docs() -> None:
    index = FakeIndex()
    index.upsert("A13", [Chunk("A13:d", "CAMEX-1", {"chunker": "A"})])
    index.delete_document("A13")
    assert not index.has_document("A13")
    index.upsert("A13", [Chunk("A13:d", "CAMEX-1", {"chunker": "A"})])
    assert index.has_document("A13")


def test_fake_index_search_filters_doc_kind_fecha_numero() -> None:
    index = FakeIndex()
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:1",
                "tipo de cambio de referencia 2002",
                {"doc_kind": "comunicacion", "fecha": "2002-03-01", "numero": "A3500"},
            )
        ],
    )
    index.upsert(
        "A8359",
        [
            Chunk(
                "A8359:1",
                "tipo de cambio de referencia vigente",
                {"doc_kind": "comunicacion", "fecha": "2025-09-01", "numero": "A8359"},
            )
        ],
    )
    index.upsert(
        "texto_ordenado",
        [
            Chunk(
                "texto_ordenado:1",
                "tipo de cambio de referencia TO",
                {"doc_kind": "texto_ordenado", "fecha": "2025-08-25", "numero": "texto_ordenado"},
            )
        ],
    )
    later = index.search(
        "tipo de cambio de referencia",
        k=5,
        filters={"doc_kind": "comunicacion", "fecha": {"$gt": "2025-08-25"}},
    )
    assert [c.metadata["doc_id"] for c in later] == ["A8359"]
    by_num = index.search(
        "tipo de cambio",
        k=5,
        filters={"numero": {"$gt": "A8307"}},
    )
    assert [c.metadata["doc_id"] for c in by_num] == ["A8359"]


def test_chroma_search_and_fecha_filter(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())
    index.upsert(
        "A8359",
        [
            Chunk(
                "A8359:d",
                "regla post TO tipo de cambio de referencia",
                {
                    "doc_kind": "comunicacion",
                    "fecha": "2025-09-01",
                    "numero": "A8359",
                    "chunker": "A",
                },
            )
        ],
    )
    hits = index.search(
        "tipo de cambio de referencia",
        k=3,
        filters={"doc_kind": "comunicacion", "fecha": {"$gt": "2025-08-25"}},
    )
    assert hits
    assert hits[0].metadata["doc_id"] == "A8359"
    assert "score" in hits[0].metadata


def test_chroma_search_retries_after_value_error(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())

    class StubCollection:
        def __init__(self) -> None:
            self.calls = 0

        def count(self) -> int:
            return 2

        def query(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls == 1:
                raise ValueError("n_results too large")
            return {
                "ids": [["A8359:1"]],
                "documents": [["post TO tipo de cambio"]],
                "metadatas": [[{"doc_id": "A8359", "doc_kind": "comunicacion"}]],
                "distances": [[0.1]],
            }

    stub = StubCollection()
    index._collection = stub  # type: ignore[attr-defined]
    hits = index.search("tipo de cambio", k=1)
    assert stub.calls == 2
    assert hits
    assert hits[0].metadata["doc_id"] == "A8359"


def test_chroma_search_empty_collection_skips_query(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())

    class EmptyCollection:
        def count(self) -> int:
            return 0

        def query(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("query should not run")

    index._collection = EmptyCollection()  # type: ignore[attr-defined]
    assert index.search("MULC") == []


def test_chroma_get_section_falls_back_when_punto_missing(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())
    index.upsert(
        "A3500",
        [
            Chunk(
                "A3500:d",
                "extracto truncado del tipo de cambio de referencia",
                {"doc_kind": "comunicacion", "chunker": "A"},
            )
        ],
    )
    text = index.get_section("A3500", "9.9.9")
    assert "tipo de cambio" in text


def test_chroma_upsert_batches_chunks(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, embedding_batch_size=2)
    index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())

    class StubCollection:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def upsert(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(kwargs)

    stub = StubCollection()
    index._collection = stub  # type: ignore[attr-defined]
    index.upsert(
        "A13",
        [
            Chunk("A13:1", "uno", {"chunker": "A"}),
            Chunk("A13:2", "dos", {"chunker": "A"}),
            Chunk("A13:3", "tres", {"chunker": "A"}),
        ],
    )
    assert len(stub.calls) == 2
    assert stub.calls[0]["ids"] == ["A13:1", "A13:2"]
    assert stub.calls[1]["ids"] == ["A13:3"]
    assert stub.calls[0]["documents"] == ["uno", "dos"]


def test_chroma_smoke_with_deterministic_embeddings(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    index = ChromaIndex(settings, embedding_function=DeterministicEmbeddingFunction())
    chunks = StructuredChunker().chunk(
        "texto_ordenado",
        "Sección 1.\n1. Una cláusula vigente.\n",
        {"doc_kind": "texto_ordenado"},
    )
    index.upsert("texto_ordenado", chunks)
    assert index.has_document("texto_ordenado")
    assert chunks[0].metadata["chunker"] == "B"
    assert "cláusula" in index.get_section("texto_ordenado")
