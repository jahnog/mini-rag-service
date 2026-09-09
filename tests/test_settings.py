from pathlib import Path

import pytest

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

def test_eval_settings_are_not_on_chat_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bcra_rag.evals.settings import EvalSettings

    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    settings = Settings(data_dir=tmp_path)
    assert not hasattr(settings, "judge_model")
    assert not hasattr(settings, "phoenix_api_key")
    eval_settings = EvalSettings(_env_file=None)
    assert eval_settings.judge_model == "grok-4.3"
    assert eval_settings.judge_reasoning_effort == "none"
    assert eval_settings.phoenix_api_key == ""


def test_eval_settings_load_phoenix_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from bcra_rag.evals.settings import EvalSettings

    monkeypatch.setenv("PHOENIX_API_KEY", "pk-test")
    eval_settings = EvalSettings(_env_file=None)
    assert eval_settings.phoenix_api_key == "pk-test"


def test_chat_settings_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://api.x.ai/v1")
    monkeypatch.delenv("EMBEDDING_MAX_CHARS", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_S", raising=False)
    settings = Settings(data_dir=tmp_path, _env_file=None)
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
    assert settings.llm_enable_thinking is True
    assert settings.llm_timeout_s == 60.0


def test_readme_how_to_run_names_auth_vars() -> None:
    readme = Path(__file__).resolve().parents[1] / "README.md"
    how = readme.read_text(encoding="utf-8").split("## How to run", 1)[1].split("### ", 1)[0]
    for name in (
        "AUTH_SECRET",
        "AUTH_ALLOWED_EMAILS",
        "AUTH_SMTP_HOST",
        "AUTH_TRUST_PROXY",
        "AUTH_PUBLIC_ORIGIN",
        "AUTH_SMTP_TIMEOUT_S",
        "bcra_rag.auth",
        "/auth/verify",
    ):
        assert name in how


def test_readme_debug_names_local_qwen_thinking() -> None:
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")
    debug = text.split("### Debug", 1)[1].split("### ", 1)[0]
    assert "Qwen3.6-35B-A3B" in debug
    assert "LLM_ENABLE_THINKING" in debug
    assert "LLM_TIMEOUT_S" in debug
    assert "LLM_BASE_URL" in debug
