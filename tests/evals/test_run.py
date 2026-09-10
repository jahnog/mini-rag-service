from __future__ import annotations

import json
from pathlib import Path

import pytest

from bcra_rag.adapters.index_fake import FakeIndex
from bcra_rag.adapters.llm_fake import FakeLlm
from bcra_rag.composition import default_pipeline
from bcra_rag.evals.adapters.judge_fake import FakeJudge
from bcra_rag.evals.adapters.sink_noop import NoOpEvalSink
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
        deterministic_only=True,
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
    assert data["judge"]["skipped"] is True
    assert data["phoenix"]["exported"] is False
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
        deterministic_only=True,
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
        deterministic_only=True,
        judge=FakeJudge(),
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
    from bcra_rag.domain.guardrails.pipeline import NoOpTracer
    from bcra_rag.evals.use_cases.run_l1 import _demo_manifest, _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    rows = load_gold(GOLD)
    samples = run_retrieval(rows, index, _demo_manifest(), tracer=NoOpTracer())
    by_id = {sample.gold.id: sample for sample in samples}
    assert by_id["g13"].retrieved_ids == [] or by_id["g13"].silencio
    vigente = by_id["g05"]
    assert "texto_ordenado" in vigente.retrieved_ids or vigente.hits


@pytest.mark.asyncio
async def test_a9999_skips_judged_generation(tmp_path: Path) -> None:
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
    assert samples[0].usable_context is False
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
        deterministic_only=True,
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
        deterministic_only=True,
    )
    later = _l1_events(log_file.read_text(encoding="utf-8"))
    assert later[-1]["unpublished"] is False


def test_shipped_l1_fixture_is_sample() -> None:
    data = json.loads((ROOT / "evals" / "l1.json").read_text(encoding="utf-8"))
    assert data.get("unpublished") or data.get("sample")
    assert data["headline_metric"] == "citation_id_exact"
    assert "ragas" not in data
    assert data["judge"]["skipped"] is True
    assert data["generation"]["skipped"] is True
    assert data["citation_id_exact"] is None


@pytest.mark.asyncio
async def test_sink_failure_still_writes(tmp_path: Path) -> None:
    class Boom(NoOpEvalSink):
        def record(self, report, *, retrieval, generation) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("collector down")

    out = tmp_path / "l1.json"
    data = await run_l1(
        gold_path=GOLD,
        output_path=out,
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        sink=Boom(),
        suites="retrieval",
        deterministic_only=True,
    )
    assert out.is_file()
    assert data["phoenix"]["exported"] is False


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


class _StubIndex:
    def __init__(self, text: str = "", boom: bool = False) -> None:
        self.text = text
        self.boom = boom
        self.search_calls: list[str] = []

    def upsert(self, doc_id: str, chunks: object) -> None:
        del doc_id, chunks

    def has_document(self, doc_id: str) -> bool:
        del doc_id
        return False

    def delete_document(self, doc_id: str) -> None:
        del doc_id

    def search(self, query: str, *, k: int = 5, filters: object = None) -> list[object]:
        del k, filters
        self.search_calls.append(query)
        return []

    def get_section(self, doc_id: str, punto: str | None = None) -> str:
        del punto
        if self.boom:
            raise RuntimeError("no section")
        if doc_id == "texto_ordenado":
            return self.text
        return ""


class _FixedCiteLlm:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, prompt: str, *, on_thinking: object = None) -> LlmDraft:
        del on_thinking
        self.calls.append(prompt)
        return LlmDraft(
            answer="Fuente: A8359",
            finding=Finding.DEFINICION,
            citations=[Citation(id="A8359", tipo="A", snippet="tipo de cambio")],
        )


class _YesSink:
    def record(self, report: object, *, retrieval: object, generation: object) -> bool:
        del report, retrieval, generation
        return True


@pytest.mark.asyncio
async def test_run_l1_exported_true_when_sink_returns_true(tmp_path: Path) -> None:
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        sink=_YesSink(),
        suites="retrieval",
        deterministic_only=True,
    )
    assert data["phoenix"]["exported"] is True


@pytest.mark.asyncio
async def test_payload_project_comes_from_settings(tmp_path: Path) -> None:
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        suites="retrieval",
        deterministic_only=True,
        phoenix_project="other-project",
    )
    assert data["phoenix"]["project"] == "other-project"


@pytest.mark.asyncio
async def test_missing_extra_skips_judge_with_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bcra_rag.evals.composition import build_evals
    from bcra_rag.evals.settings import EvalSettings

    monkeypatch.setattr("bcra_rag.evals.composition.find_spec", lambda _name: None)
    app = build_evals(
        Settings(data_dir=tmp_path),
        EvalSettings(_env_file=None, judge_api_key="secret", llm_api_key=""),
        index=FakeIndex(),
        llm=FakeLlm(),
    )
    assert app.judge is None
    assert app.judge_skip_reason == "missing_extra"
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        judge=app.judge,
        judge_skip_reason=app.judge_skip_reason,
        suites="retrieval",
        deterministic_only=False,
    )
    assert data["judge"]["skipped"] is True
    assert data["judge"]["skip_reason"] == "missing_extra"
    assert "hit_at_5" in data["retrieval"]
    assert "context_precision" not in data["retrieval"]
    assert data["retrieval"].get("context_precision") is None


def test_no_key_skip_reason_is_no_judge(tmp_path: Path) -> None:
    from bcra_rag.evals.composition import build_evals
    from bcra_rag.evals.settings import EvalSettings

    app = build_evals(
        Settings(data_dir=tmp_path),
        EvalSettings(_env_file=None, judge_api_key="", llm_api_key=""),
        index=FakeIndex(),
        llm=FakeLlm(),
    )
    assert app.judge is None
    assert app.judge_skip_reason == "no_judge"


@pytest.mark.asyncio
async def test_run_l1_copies_judge_usage(tmp_path: Path) -> None:
    judge = FakeJudge()
    judge._model = "grok-test"  # type: ignore[attr-defined]
    judge.tokens_in = 4
    judge.tokens_out = 6
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        judge=judge,
        suites="retrieval",
        deterministic_only=False,
    )
    assert data["judge"]["model"] == "grok-test"
    assert data["judge"]["calls"] == len(judge.calls)
    assert data["judge"]["tokens_in"] == 4
    assert data["judge"]["tokens_out"] == 6


@pytest.mark.asyncio
async def test_to_without_punto_skips_judged_generation(tmp_path: Path) -> None:
    from bcra_rag.evals.domain.metrics import AnswerRelevancy, Faithfulness
    from bcra_rag.evals.use_cases.run_generation import run_generation
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    rows = [row for row in load_gold(GOLD) if row.id == "g03"]
    samples = await run_generation(
        rows,
        settings=settings,
        index=index,
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        context_source="oracle",
    )
    assert samples[0].usable_context is False
    assert Faithfulness(FakeJudge()).score(samples[0]) is None
    assert AnswerRelevancy(FakeJudge()).score(samples[0]) is None


@pytest.mark.asyncio
async def test_com_a_without_punto_is_usable(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_generation import run_generation
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    rows = [row for row in load_gold(GOLD) if row.id == "g26"]
    samples = await run_generation(
        rows,
        settings=settings,
        index=index,
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        context_source="oracle",
    )
    assert samples[0].usable_context is True
    assert "Tipo de cambio de referencia 2002" in samples[0].context[0].text


@pytest.mark.asyncio
async def test_to_with_punto_is_usable(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_generation import run_generation
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    rows = [row for row in load_gold(GOLD) if row.id == "g05"]
    samples = await run_generation(
        rows,
        settings=settings,
        index=index,
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        context_source="oracle",
    )
    assert samples[0].usable_context is True


@pytest.mark.asyncio
async def test_mixed_to_and_com_a_without_punto_is_usable(tmp_path: Path) -> None:
    from bcra_rag.evals.domain.types import GoldRow
    from bcra_rag.evals.use_cases.run_generation import run_generation
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    gold = GoldRow(
        id="mix",
        question="tipo de cambio",
        gold_ids=["texto_ordenado", "A8359"],
        gold_puntos=[],
        finding="definicion",
        answerable=True,
        bucket="post-to",
    )
    samples = await run_generation(
        [gold],
        settings=settings,
        index=index,
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        context_source="oracle",
    )
    assert samples[0].usable_context is True


@pytest.mark.asyncio
async def test_retrieval_only_null_headline_citation(tmp_path: Path) -> None:
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=FakeIndex(),
        suites="retrieval",
        deterministic_only=True,
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
        deterministic_only=True,
        unpublished=False,
    )
    assert data["retrieval"]["skipped"] is True
    assert data["hit_at_5"] is None
    assert data["mrr"] is None
    assert isinstance(data["citation_id_exact"], float)


@pytest.mark.asyncio
async def test_chunking_uses_get_section_not_fakeindex_docs(tmp_path: Path) -> None:
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=_StubIndex("3.8.5 Los residentes deberán liquidar el cobro de exportaciones."),
        suites="retrieval",
        deterministic_only=True,
    )
    assert data["chunking"]["A"] > 0
    assert data["chunking"]["B"] > 0
    assert "texto_ordenado" in data["chunking"]["b_documents"]


@pytest.mark.asyncio
async def test_chunking_empty_when_get_section_raises(tmp_path: Path) -> None:
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=_StubIndex(boom=True),
        suites="retrieval",
        deterministic_only=True,
    )
    assert (tmp_path / "l1.json").is_file()
    assert data["chunking"]["A"] == 0
    assert data["chunking"]["B"] == 0
    assert data["chunking"]["b_documents"] == []


@pytest.mark.asyncio
async def test_seeded_fakeindex_still_reports_to(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=index,
        suites="retrieval",
        deterministic_only=True,
    )
    assert "texto_ordenado" in data["chunking"]["b_documents"]
    assert data["chunking"]["A"] > 0
    assert data["chunking"]["B"] > 0


@pytest.mark.asyncio
async def test_retrieved_context_reuses_same_run_hits(tmp_path: Path) -> None:
    from bcra_rag.domain.guardrails.pipeline import NoOpTracer
    from bcra_rag.evals.use_cases.run_generation import run_generation
    from bcra_rag.evals.use_cases.run_l1 import _demo_manifest, _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    settings = Settings(data_dir=tmp_path)
    rows = load_gold(GOLD)
    retrieval = run_retrieval(rows, index, _demo_manifest(), tracer=NoOpTracer())
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
        deterministic_only=True,
    )
    assert data["citation_id_exact"] == data["generation"]["citation_id_exact"]
    assert data["hit_at_5"] == data["retrieval"]["hit_at_5"]
    assert data["citation_id_exact"] != data["hit_at_5"]


@pytest.mark.asyncio
async def test_precision_at_5_distinct_from_context_precision(tmp_path: Path) -> None:
    from bcra_rag.evals.use_cases.run_l1 import _seed_demo_index

    index = FakeIndex()
    _seed_demo_index(index)
    data = await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=Settings(data_dir=tmp_path),
        index=index,
        judge=FakeJudge(),
        suites="retrieval",
        deterministic_only=False,
    )
    assert "precision_at_5" in data["retrieval"]
    assert "context_precision" in data["retrieval"]


@pytest.mark.asyncio
async def test_oracle_generation_emits_no_retriever_span(tmp_path: Path) -> None:
    from tests.evals.test_tracer import RecordingTracer

    settings = Settings(data_dir=tmp_path)
    tracer = RecordingTracer()
    await run_l1(
        gold_path=GOLD,
        output_path=tmp_path / "l1.json",
        settings=settings,
        index=FakeIndex(),
        llm=FakeLlm(),
        pipeline=default_pipeline(settings),
        tracer=tracer,
        suites="generation",
        generation_context="oracle",
        deterministic_only=True,
    )
    assert tracer.retriever_calls == []
