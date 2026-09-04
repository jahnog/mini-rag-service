from __future__ import annotations

from bcra_rag.adapters.session_memory import InMemorySessionStore


def test_mint_get_append_clear_expire() -> None:
    store = InMemorySessionStore(ttl_s=3600, cap=200)
    session_id = store.mint()
    store.append(session_id, "user", "hola")
    store.append(session_id, "assistant", "respuesta")
    messages = store.get(session_id)
    assert messages == [("user", "hola"), ("assistant", "respuesta")]
    store.expire()
    assert store.get(session_id)
    store.clear(session_id)
    assert store.get(session_id) == []


def test_keeps_last_six_messages() -> None:
    store = InMemorySessionStore()
    session_id = store.mint()
    for i in range(8):
        store.append(session_id, "user", f"m{i}")
    messages = store.get(session_id)
    assert len(messages) == 6
    assert messages[0][1] == "m2"
    assert messages[-1][1] == "m7"


def test_cap_evicts_oldest() -> None:
    store = InMemorySessionStore(cap=2)
    first = store.mint()
    store.append(first, "user", "keep-me-not")
    second = store.mint()
    store.append(second, "user", "second")
    third = store.mint()
    store.append(third, "user", "third")
    assert store.get(first) == []
    assert store.get(second)
    assert store.get(third)


def test_ttl_expires_idle_session() -> None:
    import time

    store = InMemorySessionStore(ttl_s=60)
    session_id = store.mint()
    store.append(session_id, "user", "old")
    store._sessions[session_id].updated = time.time() - 120
    assert store.get(session_id) == []
