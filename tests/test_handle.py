from __future__ import annotations

from types import SimpleNamespace

from bcra_rag.api.handle import client_id_for, demo_key_for


def test_client_id_uses_forwarded_for() -> None:
    request = SimpleNamespace(headers={"x-forwarded-for": "10.1.2.3, 10.0.0.1"}, client=None)
    assert client_id_for(request) == "10.1.2.3"


def test_client_id_unknown_without_client() -> None:
    request = SimpleNamespace(headers={}, client=None)
    assert client_id_for(request) == "unknown"


def test_demo_key_from_bearer() -> None:
    request = SimpleNamespace(headers={"authorization": "Bearer secret-token"})
    assert demo_key_for(request) == "secret-token"
