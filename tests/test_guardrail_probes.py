from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

import pytest

from bcra_rag.composition import default_pipeline
from bcra_rag.domain.guardrails.input import LengthRail
from bcra_rag.domain.guardrails.pipeline import GuardrailPipeline
from bcra_rag.domain.guardrails.retrieve import ContextBudgetRail
from bcra_rag.domain.guardrails.types import RailContext
from bcra_rag.domain.models import Chunk
from bcra_rag.schemas import Citation, Finding
from bcra_rag.settings import Settings
from bcra_rag.use_cases.run_l1 import load_gold

ROOT = Path(__file__).resolve().parents[1]
PROBES = Path(__file__).parent / "fixtures" / "guardrail_probes.jsonl"
GOLD = ROOT / "evals" / "gold.jsonl"
SK = "sk-abcdefghijklmnopqrstuvwxyz"
LM = "lm-abcdefghijklmnopqrstuvwxyz"
XAI = "xai-abcdefghijklmnopqrstuvwxyz"
GHP = "ghp_abcdefghijklmnopqrst"

REQUIRED = {
    "id",
    "source",
    "rail",
    "stage",
    "lang",
    "user_query",
    "expected",
    "status",
    "data",
}
VERDICTS = {"pass", "warn", "block", "redact"}
STATUSES = {"assert", "gap"}
LANGS = {"en", "es", "de", "zxx"}
POLICY_RAILS = {
    "length",
    "normalize",
    "secrets",
    "no-advice",
    "injection",
    "scope",
    "chunk-injection",
    "chunk-hygiene",
    "context-budget",
    "cite-or-abstain",
    "freeze-honesty",
    "no-advice-output",
    "secrets-output",
    "prompt-leak",
    "unsafe-output",
    "markdown-sanitize",
}


class Probe(TypedDict, total=False):
    id: str
    source: str
    rail: str
    stage: str
    lang: str
    user_query: bool
    expected: Literal["pass", "warn", "block", "redact"]
    status: Literal["assert", "gap"]
    data: str
    answer: str
    hits: list[dict[str, str]]
    citations: list[dict[str, str]]
    finding: str
    last_refresh: str
    to_as_of: str
    delimiter: str
    max_chars: int
    before: list[str]


def _load_probes() -> list[Probe]:
    rows: list[Probe] = []
    for line_no, line in enumerate(PROBES.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        raw = json.loads(line)
        missing = REQUIRED - raw.keys()
        if missing:
            raise AssertionError(f"{PROBES}:{line_no} missing {sorted(missing)}")
        if raw["expected"] not in VERDICTS:
            raise AssertionError(f"{PROBES}:{line_no} bad expected {raw['expected']}")
        if raw["status"] not in STATUSES:
            raise AssertionError(f"{PROBES}:{line_no} bad status {raw['status']}")
        if raw["lang"] not in LANGS:
            raise AssertionError(f"{PROBES}:{line_no} bad lang {raw['lang']}")
        if not isinstance(raw["user_query"], bool):
            raise AssertionError(f"{PROBES}:{line_no} user_query must be bool")
        if raw["user_query"] and raw["lang"] not in {"en", "es", "de"}:
            raise AssertionError(f"{PROBES}:{line_no} user_query lang must be en/es/de")
        rows.append(cast(Probe, raw))
    return rows


PROBES_ROWS = _load_probes()


def _ctx(probe: Probe) -> RailContext:
    hits = [
        Chunk(
            chunk_id=item.get("chunk_id") or f"c{index}",
            text=item["text"],
            metadata={"doc_id": item.get("doc_id") or "A1"},
        )
        for index, item in enumerate(probe.get("hits") or [])
    ]
    citations = [
        Citation(
            id=item["id"],
            tipo=cast(Any, item.get("tipo") or "A"),
            snippet=item.get("snippet") or "",
        )
        for item in probe.get("citations") or []
    ]
    finding_raw = probe.get("finding")
    finding = Finding(finding_raw) if finding_raw else Finding.SILENCIO
    data = probe["data"]
    turn_ids = {str(chunk.metadata.get("doc_id") or "") for chunk in hits}
    return RailContext(
        raw=data,
        text=data,
        hits=hits,
        answer=probe.get("answer") or "",
        finding=finding,
        citations=citations,
        turn_ids=turn_ids,
        last_refresh=probe.get("last_refresh"),
        to_as_of=probe.get("to_as_of"),
        delimiter=probe.get("delimiter") or "",
    )


def _pipeline_for(probe: Probe) -> GuardrailPipeline:
    max_chars = probe.get("max_chars")
    rail_id = probe["rail"]
    if rail_id == "length" and max_chars is not None:
        return GuardrailPipeline([LengthRail(int(max_chars))])
    if rail_id == "context-budget" and max_chars is not None:
        return GuardrailPipeline([ContextBudgetRail(int(max_chars))])
    return default_pipeline(Settings())


def _run_probe(probe: Probe) -> Any:
    ctx = _ctx(probe)
    pipe = _pipeline_for(probe)
    names = list(probe.get("before") or [])
    names.append(probe["rail"])
    results = pipe.run_named(names, ctx)
    return results[-1]


def _cases() -> list[Any]:
    out: list[Any] = []
    for probe in PROBES_ROWS:
        mark = pytest.mark.xfail(
            strict=False, reason="regex backend; documented miss"
        )
        param = pytest.param(
            probe,
            id=probe["id"],
            marks=mark if probe["status"] == "gap" else (),
        )
        out.append(param)
    return out


def test_user_query_stems_are_en_es_de_triplets() -> None:
    stems: dict[str, set[str]] = defaultdict(set)
    for probe in PROBES_ROWS:
        if not probe["user_query"]:
            continue
        stem, lang = probe["id"].rsplit(".", 1)
        stems[stem].add(lang)
    missing = {
        stem: sorted(langs)
        for stem, langs in stems.items()
        if langs != {"en", "es", "de"}
    }
    assert missing == {}, missing


def test_corpus_covers_every_policy_rail() -> None:
    have = {probe["rail"] for probe in PROBES_ROWS}
    assert POLICY_RAILS <= have, sorted(POLICY_RAILS - have)


@pytest.mark.parametrize("probe", _cases())
def test_probe_verdict(probe: Probe) -> None:
    result = _run_probe(probe)
    assert result.verdict == probe["expected"], result.detail
    if probe["rail"] in {"secrets", "secrets-output"}:
        assert SK not in result.detail
        assert LM not in result.detail
        assert XAI not in result.detail
        assert GHP not in result.detail
        assert "sk-" not in result.detail
        assert "lm-" not in result.detail
        assert "xai-" not in result.detail
        assert "ghp_" not in result.detail


@pytest.mark.parametrize(
    "question",
    [
        pytest.param(row["question"], id=row["id"])
        for row in load_gold(GOLD)
        if row.get("answerable")
    ],
)
def test_gold_answerable_passes_injection_no_advice_secrets(question: str) -> None:
    ctx = RailContext(raw=question, text=question)
    pipe = default_pipeline(Settings())
    for rail_id in ("injection", "no-advice", "secrets"):
        result = pipe.run_named([rail_id], ctx)[0]
        assert result.verdict == "pass", (rail_id, result.detail, question)


def test_gold_banxico_is_scope_block() -> None:
    rows = {row["id"]: row for row in load_gold(GOLD)}
    question = rows["g15"]["question"]
    ctx = RailContext(raw=question, text=question)
    result = default_pipeline(Settings()).run_named(["scope"], ctx)[0]
    assert result.verdict == "block"
