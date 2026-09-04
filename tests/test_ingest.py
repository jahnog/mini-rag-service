from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from bcra_rag.adapters.http_fetch import PoliteFetcher
from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import CatalogDocument
from bcra_rag.domain.urls import TO_DOC_ID, TO_PDF_URL
from bcra_rag.logconfig import configure_logging
from bcra_rag.settings import Settings
from bcra_rag.use_cases.ingest_corpus import IngestCorpus

A13 = CatalogDocument(
    comm_id="A13",
    title="CAMEX-1",
    url="https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A0013.pdf",
    fecha_emision=date(1981, 3, 2),
)
A100 = CatalogDocument(
    comm_id="A100",
    title="Actualización del texto ordenado. Hojas de reemplazo",
    url="https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A0100.pdf",
    fecha_emision=date(2001, 1, 1),
)
A8464 = CatalogDocument(
    comm_id="A8464",
    title="Exterior y Cambios. Adecuaciones.",
    url="https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8464.pdf",
    fecha_emision=date(2026, 8, 6),
)
A8465 = CatalogDocument(
    comm_id="A8465",
    title="Nueva",
    url="https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8465.pdf",
    fecha_emision=date(2026, 9, 1),
)

TO_TEXT = (
    "Última comunicación incorporada: A 8307 (25/08/2025)\n"
    "Sección 1.\n1. Los residentes deberán liquidar.\n"
)
A13_TEXT = "CAMEX-1 founding circular body " * 20
EVENT_TEXT = "Hojas de reemplazo del texto ordenado."
A8464_TEXT = "Sección 2.\n1. Adecuación posterior.\n"


class FakeCatalog:
    def __init__(self, docs: list[CatalogDocument]) -> None:
        self.docs = list(docs)
        self.calls = 0

    async def list_camex_a(self) -> list[CatalogDocument]:
        self.calls += 1
        return list(self.docs)


class ScriptedExtractor:
    def extract_pdf(self, raw_bytes: bytes) -> str:
        return raw_bytes.split(b"\n", 1)[-1].decode("utf-8")


def _pdf(text: str) -> bytes:
    return b"%PDF-1.4\n" + text.encode()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, download_concurrency=2, download_delay_s=0.0)


def _usecase(
    settings: Settings,
    docs: list[CatalogDocument],
    index: FakeIndex | None = None,
) -> tuple[IngestCorpus, FakeCatalog, FakeIndex]:
    catalog = FakeCatalog(docs)
    fake_index = index or FakeIndex()
    fetcher = PoliteFetcher(settings)
    use_case = IngestCorpus(
        settings, catalog, ScriptedExtractor(), fake_index, fetcher
    )
    return use_case, catalog, fake_index


def _mock_pdfs() -> None:
    respx.get(TO_PDF_URL).mock(
        return_value=httpx.Response(
            200, content=_pdf(TO_TEXT), headers={"content-type": "application/pdf"}
        )
    )
    respx.get(A13.url).mock(
        return_value=httpx.Response(
            200, content=_pdf(A13_TEXT), headers={"content-type": "application/pdf"}
        )
    )
    respx.get(A100.url).mock(
        return_value=httpx.Response(
            200, content=_pdf(EVENT_TEXT), headers={"content-type": "application/pdf"}
        )
    )
    respx.get(A8464.url).mock(
        return_value=httpx.Response(
            200, content=_pdf(A8464_TEXT), headers={"content-type": "application/pdf"}
        )
    )
    respx.get(A8465.url).mock(
        return_value=httpx.Response(
            200, content=_pdf("nuevo"), headers={"content-type": "application/pdf"}
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_empty_dump_sets_dates_and_stores_docs(settings: Settings) -> None:
    _mock_pdfs()
    use_case, _, index = _usecase(settings, [A8464, A13, A100])
    await use_case.run("full")
    manifest = Manifest.load(settings.manifest_path)
    assert manifest.last_refresh
    assert manifest.to_as_of == "A8307"
    assert manifest.last_comm_id == "A8464"
    assert "A13" in manifest.documents
    assert "texto_ordenado" in manifest.documents
    assert index.has_document("A13")
    assert index.has_document("texto_ordenado")
    assert index.has_document("A100")
    assert index.docs["A100"][0].metadata["doc_kind"] == "event"


@pytest.mark.asyncio
@respx.mock
async def test_resume_continues_and_does_not_wipe(settings: Settings) -> None:
    _mock_pdfs()

    class OnceBoom(FakeIndex):
        def __init__(self) -> None:
            super().__init__()
            self._failed = False

        def upsert(self, doc_id, chunks):  # type: ignore[no-untyped-def]
            if doc_id == "A8464" and not self._failed:
                self._failed = True
                raise RuntimeError("boom")
            return super().upsert(doc_id, chunks)

    boom = OnceBoom()
    use_case, _, _ = _usecase(settings, [A13, A8464], boom)
    with pytest.raises(RuntimeError):
        await use_case.run("full")
    manifest = Manifest.load(settings.manifest_path)
    assert "A13" in manifest.documents
    assert "A8464" in manifest.documents
    assert manifest.documents["A8464"].get("indexed") is False
    assert manifest.last_refresh is None
    a8464_route = respx.get(A8464.url)
    calls_before_resume = a8464_route.call_count
    use_case2, _, index2 = _usecase(settings, [A13, A8464], FakeIndex())
    # reuse same dump dir; new empty index should repair/re-upsert remaining
    index2.docs.update(boom.docs)
    use_case2._index = index2  # type: ignore[attr-defined]
    await use_case2.run("full")
    manifest = Manifest.load(settings.manifest_path)
    assert "A13" in manifest.documents
    assert "A8464" in manifest.documents
    assert manifest.is_indexed("A8464")
    assert manifest.last_refresh
    assert a8464_route.call_count == calls_before_resume


@pytest.mark.asyncio
@respx.mock
async def test_complete_rerun_does_not_fetch_new_id(settings: Settings) -> None:
    _mock_pdfs()
    use_case, catalog, index = _usecase(settings, [A13, A8464])
    await use_case.run("full")
    catalog.docs = [A8465, A13, A8464]
    a8465_route = respx.get(A8465.url)
    await use_case.run("full")
    assert "A8465" not in Manifest.load(settings.manifest_path).documents
    assert not index.has_document("A8465")
    assert a8465_route.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_matching_sha256_skips_redownload(settings: Settings) -> None:
    _mock_pdfs()
    use_case, _, _ = _usecase(settings, [A13])
    await use_case.run("full")
    route = respx.get(A13.url)
    calls_after_first = route.call_count
    await use_case.run("full")
    assert route.call_count == calls_after_first


@pytest.mark.asyncio
@respx.mock
async def test_repair_copies_manifest_fecha_and_filters(settings: Settings) -> None:
    _mock_pdfs()
    use_case, _, index = _usecase(settings, [A13])
    await use_case.run("full")
    assert index.docs["A13"][0].metadata.get("fecha") == "1981-03-02"
    index.delete_document("A13")
    assert not index.has_document("A13")
    use_case._repair_from_disk("A13", "comunicacion", Manifest.load(settings.manifest_path))
    assert index.has_document("A13")
    assert index.docs["A13"][0].metadata.get("fecha") == "1981-03-02"
    hits = index.search("CAMEX", k=5, filters={"fecha": "1981-03-02"})
    assert hits
    assert hits[0].metadata["doc_id"] == "A13"


def _json_log_events(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        assert isinstance(payload, dict)
        events.append(payload)
    return events


@pytest.mark.asyncio
@respx.mock
async def test_progress_logs_total_current_doc_and_skips(settings: Settings) -> None:
    log_path = settings.data_dir / "logs" / "ingest.log"
    configure_logging(log_file=log_path)
    _mock_pdfs()

    class WatchingIndex(FakeIndex):
        def __init__(self) -> None:
            super().__init__()
            self.total_before_first_upsert: int | None = None

        def upsert(self, doc_id, chunks):  # type: ignore[no-untyped-def]
            if self.total_before_first_upsert is None:
                started = [
                    event
                    for event in _json_log_events(log_path)
                    if event.get("event") == "ingest_run_started"
                ]
                self.total_before_first_upsert = (
                    int(started[0]["total"]) if started else None
                )
            return super().upsert(doc_id, chunks)

    index = WatchingIndex()
    use_case, _, _ = _usecase(settings, [A8464, A13, A100], index)
    await use_case.run("full")
    assert index.total_before_first_upsert == 4

    events = _json_log_events(log_path)
    started = [event for event in events if event.get("event") == "ingest_run_started"]
    assert started
    assert started[0]["total"] == 4
    assert started[0]["mode"] == "full"

    a13 = [event for event in events if event.get("doc_id") == "A13"]
    assert a13
    assert any(event.get("name") == "CAMEX-1" for event in a13)
    assert any(event.get("fecha") == "1981-03-02" for event in a13)

    to_events = [event for event in events if event.get("doc_id") == "texto_ordenado"]
    assert any(event.get("name") == "Exterior y Cambios" for event in to_events)

    finished = [event for event in events if event.get("event") == "ingest_document_finished"]
    assert finished[-1]["processed"] == 4
    assert finished[-1]["total"] == 4

    first_count = len(events)
    await use_case.run("full")
    second = _json_log_events(log_path)[first_count:]
    second_finished = [
        event for event in second if event.get("event") == "ingest_document_finished"
    ]
    assert second_finished
    assert second_finished[-1]["processed"] == second_finished[-1]["total"]
    assert any(event.get("doc_id") == "A13" for event in second)
    assert any(event.get("fecha") == "1981-03-02" for event in second)


def test_manifest_is_indexed_and_merge(tmp_path: Path) -> None:
    path = tmp_path / "MANIFEST.json"
    manifest = Manifest(path=path)
    manifest.checkpoint("A13", {"sha256": "abc", "url": "https://www.bcra.gob.ar/a.pdf"})
    assert manifest.is_indexed("A13")
    manifest.checkpoint("A13", {"indexed": True})
    assert manifest.sha256_for("A13") == "abc"
    assert manifest.documents["A13"]["url"].endswith("/a.pdf")
    manifest.checkpoint("A8464", {"sha256": "def", "indexed": False})
    assert manifest.is_indexed("A8464") is False
    assert manifest.is_indexed("missing") is False


@pytest.mark.asyncio
@respx.mock
async def test_to_upsert_boom_does_not_redownload(settings: Settings) -> None:
    _mock_pdfs()

    class Boom(FakeIndex):
        def upsert(self, doc_id, chunks):  # type: ignore[no-untyped-def]
            if doc_id == TO_DOC_ID:
                raise RuntimeError("to boom")
            return super().upsert(doc_id, chunks)

    use_case, _, _ = _usecase(settings, [A13], Boom())
    with pytest.raises(RuntimeError, match="to boom"):
        await use_case.run("full")
    manifest = Manifest.load(settings.manifest_path)
    assert TO_DOC_ID in manifest.documents
    assert manifest.documents[TO_DOC_ID].get("indexed") is False
    to_route = respx.get(TO_PDF_URL)
    calls = to_route.call_count
    use_case2, _, index2 = _usecase(settings, [A13], FakeIndex())
    await use_case2.run("full")
    assert to_route.call_count == calls
    assert index2.has_document(TO_DOC_ID)
    assert Manifest.load(settings.manifest_path).is_indexed(TO_DOC_ID)


@pytest.mark.asyncio
@respx.mock
async def test_download_logs_for_new_id_not_for_skip(settings: Settings) -> None:
    log_path = settings.data_dir / "logs" / "ingest.log"
    configure_logging(log_file=log_path)
    _mock_pdfs()
    use_case, _, _ = _usecase(settings, [A13])
    await use_case.run("full")
    events = _json_log_events(log_path)
    started = [
        event
        for event in events
        if event.get("event") == "ingest_document_download_started"
        and event.get("doc_id") == "A13"
    ]
    assert started
    assert started[0]["url"] == A13.url
    assert started[0]["name"] == "CAMEX-1"
    assert started[0]["fecha"] == "1981-03-02"
    assert any(
        event.get("event") == "ingest_document_downloaded" and event.get("doc_id") == "A13"
        for event in events
    )
    assert any(
        event.get("event") == "ingest_document_indexed" and event.get("doc_id") == "A13"
        for event in events
    )
    first_count = len(events)
    await use_case.run("full")
    second = _json_log_events(log_path)[first_count:]
    assert not any(
        event.get("event") == "ingest_document_download_started"
        and event.get("doc_id") == "A13"
        for event in second
    )
    assert not any(
        event.get("event") == "ingest_document_downloaded" and event.get("doc_id") == "A13"
        for event in second
    )


@pytest.mark.asyncio
@respx.mock
async def test_orphan_raw_and_extract_skips_to_get(settings: Settings) -> None:
    _mock_pdfs()
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.extract_dir.mkdir(parents=True, exist_ok=True)
    (settings.raw_dir / f"{TO_DOC_ID}.pdf").write_bytes(_pdf(TO_TEXT))
    (settings.extract_dir / f"{TO_DOC_ID}.txt").write_text(TO_TEXT, encoding="utf-8")
    to_route = respx.get(TO_PDF_URL)
    use_case, _, index = _usecase(settings, [A13])
    await use_case.run("full")
    assert to_route.call_count == 0
    manifest = Manifest.load(settings.manifest_path)
    assert manifest.sha256_for(TO_DOC_ID)
    assert manifest.is_indexed(TO_DOC_ID)
    assert index.has_document(TO_DOC_ID)
    assert manifest.to_as_of == "A8307"


@pytest.mark.asyncio
@respx.mock
async def test_legacy_entry_without_indexed_skips_upsert(settings: Settings) -> None:
    _mock_pdfs()
    use_case, _, index = _usecase(settings, [A13])
    await use_case.run("full")
    manifest = Manifest.load(settings.manifest_path)
    entry = manifest.documents["A13"]
    entry.pop("indexed", None)
    manifest.save()
    index.upsert_calls.clear()
    route = respx.get(A13.url)
    calls = route.call_count
    await use_case.run("full")
    assert route.call_count == calls
    assert "A13" not in index.upsert_calls
