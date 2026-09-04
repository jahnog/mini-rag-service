from pathlib import Path

from bcra_rag.settings import Settings


def test_extra_env_keys_do_not_break_load(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TOTALLY_UNKNOWN_KEY", "should-be-ignored")
    monkeypatch.setenv("EMBEDDING_MODEL", "fake-embed")
    settings = Settings()
    assert settings.data_dir == tmp_path
    assert settings.embedding_model == "fake-embed"
    assert settings.dump_dir == tmp_path / "bcra" / "current"
    assert settings.index_dir == tmp_path / "index"


def test_chat_settings_defaults(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    assert settings.max_message_chars == 4000
    assert settings.default_k == 5
    assert settings.max_k == 8
    assert settings.rate_limit_requests == 20
    assert settings.rate_limit_window_s == 60
    assert settings.demo_api_key == ""
    assert settings.llm_base_url.startswith("https://")
    assert settings.evals_dir == Path("evals")
    assert settings.embedding_backend == "auto"
    assert settings.embedding_batch_size == 8
    assert settings.embedding_timeout_s == 120.0
    assert settings.embedding_max_chars == 2048
