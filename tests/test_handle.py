from __future__ import annotations

from types import SimpleNamespace

from bcra_rag.api.handle import client_id_for, demo_key_for


def test_client_id_uses_forwarded_for_when_trusted() -> None:
    request = SimpleNamespace(headers={"x-forwarded-for": "10.1.2.3, 10.0.0.1"}, client=None)
    assert client_id_for(request, trusted_proxy=True) == "10.1.2.3"


def test_client_id_ignores_forwarded_for_by_default() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "10.1.2.3"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_id_for(request) == "127.0.0.1"


def test_client_id_unknown_without_client() -> None:
    request = SimpleNamespace(headers={}, client=None)
    assert client_id_for(request) == "unknown"


def test_demo_key_from_bearer() -> None:
    request = SimpleNamespace(headers={"authorization": "Bearer secret-token"})
    assert demo_key_for(request) == "secret-token"
