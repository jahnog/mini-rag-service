from __future__ import annotations

import asyncio
from pathlib import Path

from pytest_bdd import given, parsers, scenarios, then, when
from tests.chat_fixtures import seed_ready
from tests.test_answer_query import _uc

from bcra_rag.schemas import ChatFilters, ChatRequest
from bcra_rag.use_cases.answer_query import AnswerQuery

scenarios("chat.feature")


@given("a ready CAMEX index", target_fixture="world")
def ready_index(tmp_path: Path) -> dict[str, object]:
    use_case, llm = _uc(tmp_path)
    settings, index, manifest = seed_ready(tmp_path)
    return {
        "use_case": use_case,
        "llm": llm,
        "manifest": manifest,
        "settings": settings,
        "index": index,
        "calls_before_clear": 0,
        "response": None,
        "session_id": None,
    }


def _await(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


@when(parsers.parse('the user asks "{message}"'))
def user_asks(world: dict[str, object], message: str) -> None:
    use_case = world["use_case"]
    assert isinstance(use_case, AnswerQuery)
    response = _await(
        use_case.run(
            ChatRequest(message=message, session_id=world["session_id"]),  # type: ignore[arg-type]
            request_id="bdd",
        )
    )
    world["response"] = response
    world["session_id"] = response.session_id  # type: ignore[union-attr]


@when(
    parsers.parse(
        'the user asks "{message}" with tipo A filters'
    )
)
def user_asks_filtered(world: dict[str, object], message: str) -> None:
    use_case = world["use_case"]
    assert isinstance(use_case, AnswerQuery)
    world["response"] = _await(
        use_case.run(
            ChatRequest(message=message, filters=ChatFilters(tipo=["A"])),
            request_id="bdd-f",
        )
    )


@when("the user clears the session")
def user_clears(world: dict[str, object]) -> None:
    llm = world["llm"]
    world["calls_before_clear"] = len(llm.calls)  # type: ignore[arg-type]
    use_case = world["use_case"]
    assert isinstance(use_case, AnswerQuery)
    world["response"] = _await(
        use_case.run(
            ChatRequest(message="/clear", session_id=world["session_id"]),  # type: ignore[arg-type]
            request_id="bdd-c",
        )
    )


@then("the answer includes a Fuente line")
def fuente(world: dict[str, object]) -> None:
    assert "Fuente:" in world["response"].answer  # type: ignore[union-attr]


@then("each citation id exists in the dump")
def citations_in_dump(world: dict[str, object]) -> None:
    manifest = world["manifest"]
    response = world["response"]
    dump_ids = set(manifest.documents)  # type: ignore[union-attr]
    for citation in response.citations:  # type: ignore[union-attr]
        assert citation.id in dump_ids


@then("finding is not silencio")
def not_silencio(world: dict[str, object]) -> None:
    assert world["response"].finding.value != "silencio"  # type: ignore[union-attr]


@then("finding is silencio")
def is_silencio(world: dict[str, object]) -> None:
    assert world["response"].finding.value == "silencio"  # type: ignore[union-attr]


@then("the no-advice rule is block")
def no_advice_block(world: dict[str, object]) -> None:
    _rule(world, "no-advice", "block")


@then("the injection rule is block")
def injection_block(world: dict[str, object]) -> None:
    _rule(world, "injection", "block")


@then("the scope rule is block")
def scope_block(world: dict[str, object]) -> None:
    _rule(world, "scope", "block")


@then("the language model is not called")
def llm_not_called(world: dict[str, object]) -> None:
    assert world["llm"].calls == []  # type: ignore[union-attr]


@then("the language model was not called for clear")
def llm_not_called_clear(world: dict[str, object]) -> None:
    llm = world["llm"]
    assert len(llm.calls) == world["calls_before_clear"]  # type: ignore[arg-type]


@then(parsers.parse('a citation id is "{doc_id}"'))
def citation_id(world: dict[str, object], doc_id: str) -> None:
    ids = [c.id for c in world["response"].citations]  # type: ignore[union-attr]
    assert doc_id in ids


@then("the answer does not reveal hidden instructions")
def no_leak(world: dict[str, object]) -> None:
    answer = world["response"].answer.lower()  # type: ignore[union-attr]
    assert "system prompt" not in answer
    assert "quoted clauses stay in spanish" not in answer


@then("the answer names last_refresh and to_as_of")
def names_dates(world: dict[str, object]) -> None:
    answer = world["response"].answer  # type: ignore[union-attr]
    assert world["response"].last_refresh in answer  # type: ignore[union-attr]
    assert world["response"].to_as_of in answer  # type: ignore[union-attr]


@then("the clear response has no citations")
def clear_no_citations(world: dict[str, object]) -> None:
    assert world["response"].citations == []  # type: ignore[union-attr]


@then("remaining citations are tipo A")
def tipo_a(world: dict[str, object]) -> None:
    assert all(c.tipo == "A" for c in world["response"].citations)  # type: ignore[union-attr]


@then("none are texto ordenado")
def no_to(world: dict[str, object]) -> None:
    assert all(c.id != "texto_ordenado" for c in world["response"].citations)  # type: ignore[union-attr]


def _rule(world: dict[str, object], name: str, verdict: str) -> None:
    log = world["response"].guardrails  # type: ignore[union-attr]
    match = next(item for item in log if item.rule == name)
    assert match.verdict == verdict
