from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from bcra_rag.domain.health import dump_health
from bcra_rag.domain.manifest import Manifest
from bcra_rag.evals.composition import build_evals
from bcra_rag.evals.use_cases.run_l1 import SuiteChoice, run_l1
from bcra_rag.logconfig import configure_logging
from bcra_rag.settings import Settings


def main() -> None:
    args = _parse()
    root = Path(__file__).resolve().parent
    settings = Settings()
    configure_logging(log_file=settings.data_dir / "logs" / "l1.log")
    app = build_evals(settings)
    health = dump_health(settings, app.index)
    ready = bool(health.index_ready)
    asyncio.run(
        run_l1(
            gold_path=root / "gold.jsonl",
            output_path=root / "l1.json",
            settings=settings,
            index=app.index if ready else None,
            llm=app.llm,
            pipeline=app.pipeline,
            manifest=Manifest.load(settings.manifest_path) if ready else None,
            judge=None if args.deterministic_only else app.judge,
            judge_skip_reason=app.judge_skip_reason,
            sink=app.sink,
            tracer=app.tracer,
            phoenix_project=app.eval_settings.phoenix_project_name,
            unpublished=not ready,
            suites=args.suites,
            generation_context=args.generation_context,
            deterministic_only=args.deterministic_only,
        )
    )


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BCRA Mini-RAG L1 evals")
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Score retrieval only",
    )
    parser.add_argument(
        "--generation-only",
        action="store_true",
        help="Score generation only",
    )
    parser.add_argument(
        "--generation-context",
        choices=("oracle", "retrieved"),
        default="oracle",
    )
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Skip the judge language model",
    )
    args = parser.parse_args()
    suites: SuiteChoice = "both"
    if args.retrieval_only and args.generation_only:
        parser.error("choose at most one of --retrieval-only / --generation-only")
    elif args.retrieval_only:
        suites = "retrieval"
    elif args.generation_only:
        suites = "generation"
    args.suites = suites
    return args


if __name__ == "__main__":
    main()
