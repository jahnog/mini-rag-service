from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from typing import Literal

import structlog

from bcra_rag.adapters.http_fetch import NonPdfError, PoliteFetcher
from bcra_rag.domain.chunkers import FixedChunker, StructuredChunker, choose_chunker
from bcra_rag.domain.classifier import DocKind, classify_title, parse_to_as_of
from bcra_rag.domain.manifest import Manifest
from bcra_rag.domain.models import CatalogDocument, Chunk
from bcra_rag.domain.notes import HOLE_NOTE
from bcra_rag.domain.urls import TO_DOC_ID, TO_PDF_URL, is_bcra_host
from bcra_rag.ports.catalog import CatalogPort
from bcra_rag.ports.extractor import ExtractorPort
from bcra_rag.ports.index import IndexPort
from bcra_rag.settings import Settings

Mode = Literal["full", "refresh"]
TO_LOG_NAME = "Exterior y Cambios"

log = structlog.get_logger(__name__)


class IngestIncompleteError(RuntimeError):
    pass


class IngestCorpus:
    def __init__(
        self,
        settings: Settings,
        catalog: CatalogPort,
        extractor: ExtractorPort,
        index: IndexPort,
        fetcher: PoliteFetcher,
    ) -> None:
        self._settings = settings
        self._catalog = catalog
        self._extractor = extractor
        self._index = index
        self._fetcher = fetcher
        max_chars = settings.embedding_max_chars
        self._fixed = FixedChunker(max_chars=max_chars)
        self._structured = StructuredChunker(max_chars=max_chars)

    async def run(self, mode: Mode) -> None:
        self._settings.dump_dir.mkdir(parents=True, exist_ok=True)
        self._settings.raw_dir.mkdir(parents=True, exist_ok=True)
        self._settings.extract_dir.mkdir(parents=True, exist_ok=True)
        manifest = Manifest.load(self._settings.manifest_path)
        if mode == "refresh":
            self._require_complete(manifest)
        documents = await self._catalog.list_camex_a()
        if mode == "full" and manifest.last_refresh:
            known = {key for key in manifest.documents if key != TO_DOC_ID}
            documents = [doc for doc in documents if doc.comm_id in known]
        total = len(documents) + 1
        log.info("ingest_run_started", mode=mode, total=total)
        processed = 0
        replace_to = mode == "refresh"

        async def ingest_to() -> None:
            await self._ingest_to(manifest, replace=replace_to)

        processed = await self._consider_document(
            processed,
            total,
            TO_DOC_ID,
            TO_LOG_NAME,
            "",
            ingest_to,
        )
        for doc in documents:
            fecha = doc.fecha_emision.isoformat() if doc.fecha_emision else ""

            async def ingest_one(current: CatalogDocument = doc) -> None:
                await self._ingest_comunicacion(current, manifest)

            processed = await self._consider_document(
                processed,
                total,
                doc.comm_id,
                doc.title,
                fecha,
                ingest_one,
            )
        if mode == "full" or mode == "refresh":
            manifest.mark_complete()
            self._write_notes()

    async def _consider_document(
        self,
        processed: int,
        total: int,
        doc_id: str,
        name: str,
        fecha: str,
        work: Callable[[], Awaitable[None]],
    ) -> int:
        log.info(
            "ingest_document_started",
            processed=processed,
            total=total,
            doc_id=doc_id,
            name=name,
            fecha=fecha,
        )
        await work()
        processed += 1
        log.info(
            "ingest_document_finished",
            processed=processed,
            total=total,
            doc_id=doc_id,
            name=name,
            fecha=fecha,
        )
        return processed

    def _require_complete(self, manifest: Manifest) -> None:
        if not manifest.has_checkpoint or not manifest.last_refresh:
            raise IngestIncompleteError(
                "one-time ingest has not completed; run python -m bcra_rag.jobs.ingest first"
            )

    async def _ingest_to(self, manifest: Manifest, *, replace: bool) -> None:
        if not is_bcra_host(TO_PDF_URL):
            return
        await self._ingest_stored(
            manifest,
            doc_id=TO_DOC_ID,
            kind=DocKind.TEXTO_ORDENADO.value,
            url=TO_PDF_URL,
            name=TO_LOG_NAME,
            fecha="",
            title="",
            replace=replace,
            parse_to=True,
            extra_checkpoint={},
        )

    async def _ingest_comunicacion(self, doc: CatalogDocument, manifest: Manifest) -> None:
        if not is_bcra_host(doc.url):
            return
        fecha = doc.fecha_emision.isoformat() if doc.fecha_emision else ""
        await self._ingest_stored(
            manifest,
            doc_id=doc.comm_id,
            kind=classify_title(doc.title).value,
            url=doc.url,
            name=doc.title,
            fecha=fecha,
            title=doc.title,
            replace=False,
            parse_to=False,
            extra_checkpoint={
                "title": doc.title,
                "fecha": fecha or None,
            },
        )

    async def _ingest_stored(
        self,
        manifest: Manifest,
        *,
        doc_id: str,
        kind: str,
        url: str,
        name: str,
        fecha: str,
        title: str,
        replace: bool,
        parse_to: bool,
        extra_checkpoint: dict[str, object],
    ) -> None:
        self._adopt_orphan(
            manifest,
            doc_id=doc_id,
            kind=kind,
            url=url,
            extra_checkpoint=extra_checkpoint,
            parse_to=parse_to,
        )
        if self._dump_matches(manifest, doc_id):
            if not manifest.is_indexed(doc_id) or not self._index.has_document(doc_id):
                self._index_from_extract(manifest, doc_id, kind)
            if not replace:
                return
        stored_hash = manifest.sha256_for(doc_id)
        if stored_hash and manifest.is_indexed(doc_id) and not replace:
            if not self._index.has_document(doc_id):
                self._index_from_extract(manifest, doc_id, kind)
            return
        log.info(
            "ingest_document_download_started",
            doc_id=doc_id,
            name=name,
            fecha=fecha,
            url=url,
        )
        try:
            raw = await self._fetcher.get_pdf(url)
        except NonPdfError:
            return
        digest = hashlib.sha256(raw).hexdigest()
        if (
            stored_hash == digest
            and manifest.is_indexed(doc_id)
            and self._index.has_document(doc_id)
        ):
            return
        extract = self._extractor.extract_pdf(raw)
        body = extract if parse_to else self._body_for_kind(kind, title, extract)
        if parse_to:
            to_as_of = parse_to_as_of(body)
            if to_as_of:
                manifest.to_as_of = to_as_of
        (self._settings.raw_dir / f"{doc_id}.pdf").write_bytes(raw)
        (self._settings.extract_dir / f"{doc_id}.txt").write_text(
            body, encoding="utf-8"
        )
        self._write_dump_checkpoint(
            manifest,
            doc_id=doc_id,
            digest=digest,
            kind=kind,
            url=url,
            extra_checkpoint=extra_checkpoint,
        )
        log.info("ingest_document_downloaded", doc_id=doc_id, sha256=digest)
        self._index_from_extract(manifest, doc_id, kind)

    def _adopt_orphan(
        self,
        manifest: Manifest,
        *,
        doc_id: str,
        kind: str,
        url: str,
        extra_checkpoint: dict[str, object],
        parse_to: bool,
    ) -> None:
        if manifest.sha256_for(doc_id):
            return
        raw_path = self._settings.raw_dir / f"{doc_id}.pdf"
        extract_path = self._settings.extract_dir / f"{doc_id}.txt"
        if not raw_path.is_file() or not extract_path.is_file():
            return
        digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if parse_to:
            to_as_of = parse_to_as_of(extract_path.read_text(encoding="utf-8"))
            if to_as_of:
                manifest.to_as_of = to_as_of
        self._write_dump_checkpoint(
            manifest,
            doc_id=doc_id,
            digest=digest,
            kind=kind,
            url=url,
            extra_checkpoint=extra_checkpoint,
        )

    def _dump_matches(self, manifest: Manifest, doc_id: str) -> bool:
        stored_hash = manifest.sha256_for(doc_id)
        raw_path = self._settings.raw_dir / f"{doc_id}.pdf"
        if not stored_hash or not raw_path.is_file():
            return False
        local = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        return local == stored_hash

    def _write_dump_checkpoint(
        self,
        manifest: Manifest,
        *,
        doc_id: str,
        digest: str,
        kind: str,
        url: str,
        extra_checkpoint: dict[str, object],
    ) -> None:
        payload: dict[str, object] = {
            "sha256": digest,
            "kind": kind,
            "url": url,
            "indexed": False,
            **extra_checkpoint,
        }
        manifest.checkpoint(doc_id, payload)

    def _index_from_extract(self, manifest: Manifest, doc_id: str, kind: str) -> None:
        extract_path = self._settings.extract_dir / f"{doc_id}.txt"
        if not extract_path.is_file():
            return
        text = extract_path.read_text(encoding="utf-8")
        entry = manifest.documents.get(doc_id, {})
        meta: dict[str, object] = {
            "doc_kind": kind,
            "numero": doc_id,
            "title": str(entry.get("title") or ""),
            "fecha": str(entry.get("fecha") or ""),
        }
        self._index.delete_document(doc_id)
        chunks = self._chunk(doc_id, kind, text, meta)
        self._index.upsert(doc_id, chunks)
        manifest.checkpoint(doc_id, {"indexed": True})
        log.info("ingest_document_indexed", doc_id=doc_id)

    def _repair_from_disk(self, doc_id: str, kind: str, manifest: Manifest) -> None:
        self._index_from_extract(manifest, doc_id, kind)

    def _chunk(
        self, doc_id: str, kind: str, text: str, metadata: dict[str, object]
    ) -> list[Chunk]:
        which = choose_chunker(kind, text)
        chunker = self._structured if which == "B" else self._fixed
        return chunker.chunk(doc_id, text, metadata)

    def _body_for_kind(self, kind: str, title: str, extract: str) -> str:
        if kind == DocKind.EVENT.value:
            return f"{title}\n{extract[:800]}"
        return extract

    def _write_notes(self) -> None:
        self._settings.notes_path.write_text(HOLE_NOTE, encoding="utf-8")
