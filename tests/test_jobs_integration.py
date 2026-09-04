from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import pytest

from bcra_rag.adapters.index_chroma import ChromaIndex
from bcra_rag.composition import IngestApp, build_ingest
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.urls import TO_DOC_ID, TO_PDF_URL
from bcra_rag.jobs.ingest import _run as ingest_run
from bcra_rag.jobs.refresh import _run as refresh_run
from bcra_rag.settings import Settings
from tests.test_ingest import FakeCatalog

_MIN_PDF_BYTES = 100 * 1024
_STALE_REFRESH = "2020-01-01T00:00:00+00:00"


def _require_pdftotext() -> None:
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext not found; install poppler-utils")


def _live_app(tmp_path: Path) -> IngestApp:
    settings = Settings(
        data_dir=tmp_path,
        download_delay_s=0.0,
        download_concurrency=2,
        embedding_api_key="",
    )
    app = build_ingest(settings)
    return IngestApp(
        settings=settings,
        catalog=FakeCatalog([]),
        extractor=app.extractor,
        index=app.index,
    )


def _assert_one_real_to(settings: Settings) -> Manifest:
    pdfs = sorted(settings.raw_dir.glob("*.pdf"))
    assert [path.name for path in pdfs] == [f"{TO_DOC_ID}.pdf"]
    raw = pdfs[0].read_bytes()
    assert raw.lstrip().startswith(b"%PDF")
    assert len(raw) > _MIN_PDF_BYTES
    extract = settings.extract_dir / f"{TO_DOC_ID}.txt"
    assert extract.is_file()
    assert extract.read_text(encoding="utf-8").strip()
    assert settings.notes_path.is_file()
    manifest = Manifest.load(settings.manifest_path)
    assert manifest.sha256_for(TO_DOC_ID) == hashlib.sha256(raw).hexdigest()
    assert manifest.last_refresh
    assert manifest.to_as_of is not None
    assert re.fullmatch(r"A\d+", manifest.to_as_of)
    index = ChromaIndex(settings)
    assert index.has_document(TO_DOC_ID)
    return manifest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_command_downloads_one_real_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_pdftotext()
    app = _live_app(tmp_path)
    monkeypatch.setattr("bcra_rag.jobs.ingest.build_ingest", lambda: app)
    assert await ingest_run() == 0
    _assert_one_real_to(app.settings)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_command_downloads_one_real_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_pdftotext()
    app = _live_app(tmp_path)
    seeded = Manifest(
        path=app.settings.manifest_path,
        last_refresh=_STALE_REFRESH,
        documents={
            TO_DOC_ID: {
                "sha256": "0" * 64,
                "kind": "texto_ordenado",
                "url": TO_PDF_URL,
            }
        },
    )
    seeded.save()
    monkeypatch.setattr("bcra_rag.jobs.refresh.build_ingest", lambda: app)
    assert await refresh_run() == 0
    manifest = _assert_one_real_to(app.settings)
    assert manifest.last_refresh != _STALE_REFRESH
