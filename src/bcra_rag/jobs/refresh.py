from __future__ import annotations

import asyncio
import sys

from bcra_rag.adapters.http_fetch import PoliteFetcher
from bcra_rag.composition import build_ingest
from bcra_rag.logconfig import configure_logging
from bcra_rag.use_cases.ingest_corpus import IngestCorpus, IngestIncompleteError


async def _run() -> int:
    app = build_ingest()
    configure_logging(log_file=app.settings.data_dir / "logs" / "ingest.log")
    fetcher = PoliteFetcher(app.settings)
    try:
        await IngestCorpus(
            app.settings, app.catalog, app.extractor, app.index, fetcher
        ).run("refresh")
    except IngestIncompleteError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
