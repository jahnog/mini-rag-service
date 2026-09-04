from __future__ import annotations

from pathlib import Path

from bcra_rag.schemas import Finding
from tests.chat_fixtures import make_client, seed_ready


def test_chat_named_a3500(tmp_path: Path) -> None:
    client, llm, _, _ = make_client(tmp_path)
    response = client.post("/chat", json={"message": "Qué dice la Comunicación A 3500?"})
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["request_id"]
    ids = [c["id"] for c in body["citations"]]
    assert "A3500" in ids
    assert llm.calls


def test_chat_clear_http(tmp_path: Path) -> None:
    client, llm, _, _ = make_client(tmp_path)
    first = client.post(
        "/chat", json={"message": "qué se exige hoy para liquidar el cobro de exportaciones"}
    ).json()
    cleared = client.post("/chat/clear", json={"session_id": first["session_id"]})
    assert cleared.status_code == 200
    body = cleared.json()
    assert body["citations"] == []
    assert body["finding"] == Finding.SILENCIO.value
    assert len(llm.calls) == 1


def test_k_cap_422(tmp_path: Path) -> None:
    client, llm, _, _ = make_client(tmp_path)
    response = client.post(
        "/chat",
        json={"message": "Qué es el MULC?", "k": 9},
    )
    assert response.status_code == 422
    assert llm.calls == []


def test_filter_comm_id_normalizes(tmp_path: Path) -> None:
    client, _, _, _ = make_client(tmp_path)
    body = client.post(
        "/chat",
        json={
            "message": "Qué dice la Comunicación A 3500?",
            "filters": {"comm_id": "A 3500"},
        },
    ).json()
    assert body["finding"] != "silencio" or body["citations"] == []
    if body["citations"]:
        assert all(c["id"] == "A3500" for c in body["citations"])


def test_filter_tipo_a(tmp_path: Path) -> None:
    client, _, _, _ = make_client(tmp_path)
    body = client.post(
        "/chat",
        json={
            "message": "qué se exige hoy para liquidar el cobro de exportaciones",
            "filters": {"tipo": ["A"]},
        },
    ).json()
    assert all(c["tipo"] == "A" for c in body["citations"])
    assert all(c["id"] != "texto_ordenado" for c in body["citations"])


def test_demo_api_key_required(tmp_path: Path) -> None:
    settings, index, _ = seed_ready(tmp_path)
    settings = settings.model_copy(update={"demo_api_key": "secret"})
    client, llm, _, _ = make_client(tmp_path, settings=settings, index=index)
    denied = client.post("/chat", json={"message": "Qué es el MULC?"})
    assert denied.status_code == 401
    ok = client.post(
        "/chat",
        json={"message": "Qué es el MULC?"},
        headers={"x-demo-key": "secret"},
    )
    assert ok.status_code == 200
    assert ok.json()["finding"] != "silencio" or ok.json()["abstain_reason"] != "scope"
    assert llm.calls


def test_rate_limit_rejects_without_full_answer(tmp_path: Path) -> None:
    settings, index, _ = seed_ready(tmp_path)
    settings = settings.model_copy(update={"rate_limit_requests": 2, "rate_limit_window_s": 60})
    client, llm, _, _ = make_client(tmp_path, settings=settings, index=index)
    client.post("/chat", json={"message": "Qué es el MULC?"})
    client.post("/chat", json={"message": "Qué es el MULC?"})
    third = client.post("/chat", json={"message": "Qué es el MULC?"})
    assert third.status_code == 429
    assert len(llm.calls) == 2


def test_disclaimer_on_every_response(tmp_path: Path) -> None:
    client, _, _, _ = make_client(tmp_path)
    body = client.post("/chat", json={"message": "Qué es el MULC?"}).json()
    assert "no oficial" in body["disclaimer"].lower()
    assert "last_refresh" in body["disclaimer"]
    silencio = client.post("/chat", json={"message": "What's the weather in Madrid?"}).json()
    assert silencio["disclaimer"]
    assert silencio["finding"] == "silencio"
