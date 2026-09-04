from __future__ import annotations

import httpx
import pytest
import respx

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.urls import TO_PDF_URL
from bcra_rag.jobs.refresh import _run as refresh_run
from bcra_rag.settings import Settings
from bcra_rag.use_cases.ingest_corpus import IngestIncompleteError
from tests.test_ingest import A13, A8464, A8465, _mock_pdfs, _pdf, _usecase


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, download_concurrency=2, download_delay_s=0.0)


@pytest.mark.asyncio
async def test_refresh_refuses_missing_dump(settings: Settings) -> None:
    use_case, catalog, _ = _usecase(settings, [])
    with pytest.raises(IngestIncompleteError, match="one-time ingest"):
        await use_case.run("refresh")
    assert catalog.calls == 0


@pytest.mark.asyncio
async def test_refresh_refuses_empty_placeholder(settings: Settings) -> None:
    settings.dump_dir.mkdir(parents=True)
    settings.manifest_path.write_text("{}", encoding="utf-8")
    use_case, catalog, _ = _usecase(settings, [A13])
    with pytest.raises(IngestIncompleteError):
        await use_case.run("refresh")
    assert catalog.calls == 0


@pytest.mark.asyncio
@respx.mock
async def test_refresh_refuses_interrupted_first_run(settings: Settings) -> None:
    _mock_pdfs()
    use_case, _, _ = _usecase(settings, [A13])

    class Boom(FakeIndex):
        def upsert(self, doc_id, chunks):  # type: ignore[no-untyped-def]
            if doc_id == "A13":
                raise RuntimeError("stop")
            return super().upsert(doc_id, chunks)

    use_case._index = Boom()  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError):
        await use_case.run("full")
    manifest = Manifest.load(settings.manifest_path)
    assert manifest.documents
    assert manifest.last_refresh is None
    use_case2, catalog2, _ = _usecase(settings, [A13])
    with pytest.raises(IngestIncompleteError, match="one-time ingest"):
        await use_case2.run("refresh")
    assert catalog2.calls == 0


@pytest.mark.asyncio
@respx.mock
async def test_refresh_appends_new_a_and_skips_unchanged_to(settings: Settings) -> None:
    _mock_pdfs()
    use_case, catalog, index = _usecase(settings, [A13, A8464])
    await use_case.run("full")
    catalog.docs = [A8465, A13, A8464]
    upserts_before = len(index.upsert_calls)
    await use_case.run("refresh")
    manifest = Manifest.load(settings.manifest_path)
    assert "A8465" in manifest.documents
    assert index.has_document("A8465")
    assert manifest.last_comm_id == "A8465"
    assert manifest.last_refresh
    to_upserts = [
        doc_id
        for doc_id in index.upsert_calls[upserts_before:]
        if doc_id == "texto_ordenado"
    ]
    assert to_upserts == []


@pytest.mark.asyncio
@respx.mock
async def test_refresh_replaces_to_and_drops_old_punto(settings: Settings) -> None:
    _mock_pdfs()
    use_case, _, index = _usecase(settings, [A13])
    await use_case.run("full")
    new_to = (
        "Última comunicación incorporada: A 8359 (01/09/2025)\n"
        "Sección 1.\n1. Cláusula nueva solamente.\n"
    )
    respx.get(TO_PDF_URL).mock(
        return_value=httpx.Response(
            200, content=_pdf(new_to), headers={"content-type": "application/pdf"}
        )
    )
    await use_case.run("refresh")
    manifest = Manifest.load(settings.manifest_path)
    assert manifest.to_as_of == "A8359"
    text = index.get_section("texto_ordenado")
    assert "Cláusula nueva" in text
    assert "Los residentes deberán liquidar" not in text


@pytest.mark.asyncio
async def test_refresh_job_exits_nonzero_on_empty(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bcra_rag.composition import IngestApp

    use_case, catalog, index = _usecase(settings, [])
    monkeypatch.setattr(
        "bcra_rag.jobs.refresh.build_ingest",
        lambda: IngestApp(
            settings=settings,
            catalog=catalog,
            extractor=use_case._extractor,  # type: ignore[attr-defined]
            index=index,
        ),
    )
    assert await refresh_run() == 1
