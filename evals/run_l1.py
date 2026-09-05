from __future__ import annotations

from pathlib import Path

from bcra_rag.adapters.index_chroma import ChromaIndex
from bcra_rag.domain.health import dump_health
from bcra_rag.domain.manifest import Manifest
from bcra_rag.logconfig import configure_logging
from bcra_rag.settings import Settings
from bcra_rag.use_cases.run_l1 import run_l1


def main() -> None:
    root = Path(__file__).resolve().parent
    settings = Settings()
    configure_logging(log_file=settings.data_dir / "logs" / "l1.log")
    index = ChromaIndex(settings)
    health = dump_health(settings, index)
    ready = bool(health.index_ready)
    run_l1(
        gold_path=root / "gold.jsonl",
        output_path=root / "l1.json",
        index=index if ready else None,
        manifest=Manifest.load(settings.manifest_path) if ready else None,
        unpublished=not ready,
    )


if __name__ == "__main__":
    main()
