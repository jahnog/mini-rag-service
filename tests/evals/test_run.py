from __future__ import annotations

import json
from pathlib import Path

import pytest

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.adapters.llm_fake import FakeLlm
from bcra_rag.composition import default_pipeline
from bcra_rag.evals.domain.gold import load_gold
from bcra_rag.evals.use_cases.oracle import oracle_chunks
from bcra_rag.evals.use_cases.run_l1 import L1_SCHEMA_KEYS, run_l1
from bcra_rag.evals.use_cases.run_retrieval import run_retrieval
from bcra_rag.logconfig import configure_logging
from bcra_rag.schemas import Citation, Finding, LlmDraft
from bcra_rag.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "evals" / "gold.jsonl"

REQUIRED_BUCKETS = {
    "definicion",
    "obligacion",
    "procedimiento",
    "silencio",
    "cross-ref",
    "superseded",
    "post-to",
    "english",
}


def test_gold_parses_and_buckets() -> None:
    rows = load_gold(GOLD)
    assert 30 <= len(rows) <= 50
    assert len(rows) == 50
    buckets = {row.bucket for row in rows}
    assert REQUIRED_BUCKETS <= buckets
    a9999 = next(row for row in rows if "9999" in row.question)
    assert a9999.finding == "silencio"
    assert a9999.gold_ids == []
    assert a9999.reference_answer is None
    refs = [row for row in rows if row.reference_answer]
    assert 8 <= len(refs) <= 12
    to_refs = [row for row in refs if "texto_ordenado" in row.gold_ids]
    assert to_refs
    assert all(row.gold_puntos for row in to_refs)
    post_refs = [row for row in refs if row.bucket == "post-to"]
    assert post_refs
    assert all("Fuente:" in (row.reference_answer or "") for row in post_refs)
    assert any(
        "A8359" in (row.reference_answer or "") or "A 8359" in (row.reference_answer or "")
        for row in post_refs
    )
    silencio = [row for row in rows if row.finding == "silencio"]
    assert all(row.reference_answer is None for row in silencio)
    english = [row for row in rows if row.bucket == "english"]
    assert english
    assert any(row.gold_puntos for row in english)


@pytest.mark.asyncio
async def test_run_l1_dry_run_schema(tmp_path: Path) -> None:
    out = tmp_path / "l1.json"
    payload = await run_l1(
        gold_path=GOLD,
        output_path=out,
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        unpublished=True,
        suites="retrieval",
    )
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    for key in L1_SCHEMA_KEYS:
        assert key in data
    assert "ragas" not in data
    assert data["headline_metric"] == "citation_id_exact"
    assert data["unpublished"] is True
    assert data["retrieval"]["skipped"] is False
    assert data["generation"]["skipped"] is True
    assert data["citation_id_exact"] is None
    assert payload["n"] == 50


@pytest.mark.asyncio
async def test_retrieval_does_not_call_llm(tmp_path: Path) -> None:
    llm = FakeLlm()
    await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        llm=llm,
        suites="retrieval",
    )
    assert llm.calls == []


@pytest.mark.asyncio
async def test_oracle_generation_does_not_search(tmp_path: Path) -> None:
    index = FakeIndex()
    settings = Settings(data_dir=tmp_path)
    payload = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=settings,
        index=index,
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        unpublished=False,
        suites="generation",
        generation_context="oracle",
    )
    assert index.search_calls == []
    assert payload["generation"]["skipped"] is False
    assert payload["generation"]["context_source"] == "oracle"
    assert payload["retrieval"]["skipped"] is True


@pytest.mark.asyncio
async def test_a3500_oracle_uses_extract(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    rows = [row for row in load_gold(GOLD) if row.id == "g26"]
    chunks = oracle_chunks(index, rows[0], settings)
    assert chunks
    assert "Tipo de cambio de referencia 2002" in chunks[0].text
    assert chunks[0].metadata["doc_id"] == "A3500"


def test_retrieval_silencio_and_vigente() -> None:
    from bcra_rag.evals.use_cases.run_l1 import _demo_manifest, _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    rows = load_gold(GOLD)
    samples = run_retrieval(rows, index, _demo_manifest())
    by_id = {sample.gold.id: sample for sample in samples}
    assert by_id["g13"].retrieved_ids == [] or by_id["g13"].silencio
    vigente = by_id["g05"]
    assert "texto_ordenado" in vigente.retrieved_ids or vigente.hits


@pytest.mark.asyncio
async def test_a9999_is_silencio_without_search(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_generation import run_generation
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    rows = [row for row in load_gold(GOLD) if row.id == "g13"]
    samples = await run_generation(
        rows,
        settings=settings,
        index=index,
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        context_source="oracle",
    )
    assert samples[0].finding is Finding.SILENCIO
    assert index.search_calls == []


@pytest.mark.asyncio
async def test_l1_run_appends_published_metrics(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "l1.log"
    configure_logging(log_file=log_file)
    out = tmp_path / "l1.json"
    settings = Settings(data_dir=tmp_path)
    await run_l1(
        gold_path=GOLD,
        output_path=out,
        settings=settings,
        index=FakeIndex(),
        unpublished=True,
        suites="retrieval",
    )
    first = _l1_events(log_file.read_text(encoding="utf-8"))
    assert first
    event = first[-1]
    assert event["headline_metric"] == "citation_id_exact"
    assert "hit_at_5" in event
    assert event["unpublished"] is True
    await run_l1(
        gold_path=GOLD,
        output_path=out,
        settings=settings,
        index=FakeIndex(),
        unpublished=False,
        suites="retrieval",
    )
    later = _l1_events(log_file.read_text(encoding="utf-8"))
    assert later[-1]["unpublished"] is False


def test_shipped_l1_fixture_is_operator_run() -> None:
    data = json.loads((ROOT / "evals" / "l1.json").read_text(encoding="utf-8"))
    assert data.get("unpublished") is False
    assert data.get("sample") is False
    assert data["headline_metric"] == "citation_id_exact"
    assert "ragas" not in data
    for key in L1_SCHEMA_KEYS:
        assert key in data
    assert data["retrieval"]["skipped"] is False
    assert data["generation"]["skipped"] is False
    assert isinstance(data["citation_id_exact"], int | float)
    assert 0.0 <= data["citation_id_exact"] <= 1.0
    assert data["generation"]["n"] > 0
    assert data["retrieval"]["n"] > 0


def _l1_events(text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("event") == "l1_run":
            events.append(data)
    return events


class _FixedCiteLlm:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(
        self, prompt: str, *, thinking: bool | None = None
    ) -> LlmDraft:
        self.calls.append(prompt)
        return LlmDraft(
            answer="Fuente: A8359",
            finding=Finding.DEFINICION,
            citations=[Citation(id="A8359", tipo="A", snippet="tipo de cambio")],
        )


@pytest.mark.asyncio
async def test_retrieval_only_null_headline_citation(tmp_path: Path) -> None:
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        suites="retrieval",
    )
    assert data["generation"]["skipped"] is True
    assert data["citation_id_exact"] is None
    assert isinstance(data["hit_at_5"], float)


@pytest.mark.asyncio
async def test_generation_only_null_retrieval_aliases(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=settings,
        index=FakeIndex(),
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        suites="generation",
        generation_context="oracle",
        unpublished=False,
    )
    assert data["retrieval"]["skipped"] is True
    assert data["hit_at_5"] is None
    assert data["mrr"] is None
    assert isinstance(data["citation_id_exact"], float)


@pytest.mark.asyncio
async def test_retrieved_context_reuses_same_run_hits(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_generation import run_generation
    from bcra_rag.evals.use_cases.run_l1 import _demo_manifest, _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    rows = load_gold(GOLD)
    retrieval = run_retrieval(rows, index, _demo_manifest())
    after_retrieval = list(index.search_calls)
    samples = await run_generation(
        rows,
        settings=settings,
        index=index,
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        context_source="retrieved",
        retrieval=retrieval,
    )
    assert index.search_calls == after_retrieval
    by_ret = {sample.gold.id: sample for sample in retrieval}
    for sample in samples:
        prior = by_ret[sample.gold.id]
        gen_ids = [str(chunk.metadata.get("doc_id") or "") for chunk in sample.context]
        hit_ids = [str(chunk.metadata.get("doc_id") or "") for chunk in prior.hits]
        assert gen_ids == hit_ids


@pytest.mark.asyncio
async def test_headline_citation_id_is_model_cites(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=settings,
        index=index,
        llm=_FixedCiteLlm(),
        pipeline=default_pipeline(settings),
        suites="both",
        unpublished=False,
    )
    assert data["citation_id_exact"] == data["generation"]["citation_id_exact"]
    assert data["hit_at_5"] == data["retrieval"]["hit_at_5"]
    assert data["citation_id_exact"] != data["hit_at_5"]


@pytest.mark.asyncio
async def test_retrieval_block_publishes_precision_at_5(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=index,
        suites="retrieval",
    )
    assert "precision_at_5" in data["retrieval"]
