from pathlib import Path

from bcra_rag.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
UNITS = (
    "bcra-rag.service",
    "bcra-rag-ingest.service",
    "bcra-rag-refresh.service",
)
PLACEHOLDER_DIR = "__DEPLOY_DIR__"
PLACEHOLDER_USER = "__DEPLOY_USER__"
RENDER_DIR = "/tmp/bcra-rag"
RENDER_USER = "svcuser"


def _read(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def _render(text: str) -> str:
    return text.replace(PLACEHOLDER_DIR, RENDER_DIR).replace(PLACEHOLDER_USER, RENDER_USER)


def test_all_units_share_working_directory_and_have_no_conflicts() -> None:
    for name in UNITS:
        text = _read(name)
        assert f"WorkingDirectory={PLACEHOLDER_DIR}" in text
        assert "Conflicts=" not in text
        assert "BindsTo=" not in text
        assert "PartOf=" not in text


def test_api_unit_invariants() -> None:
    text = _read("bcra-rag.service")
    assert f"User={PLACEHOLDER_USER}" in text
    assert f"EnvironmentFile={PLACEHOLDER_DIR}/.env" in text
    assert "EnvironmentFile=-" not in text
    assert (
        f"ExecStart={PLACEHOLDER_DIR}/.venv/bin/uvicorn "
        "bcra_rag.api.app:app --host 127.0.0.1 --port 8000"
    ) in text
    assert "--workers" not in text
    assert "Restart=always" in text
    assert "MemoryMax=" not in text
    assert "[Install]" in text
    assert "WantedBy=multi-user.target" in text
    assert "Type=oneshot" not in text
    rendered = _render(text)
    assert f"User={RENDER_USER}" in rendered
    assert f"WorkingDirectory={RENDER_DIR}" in rendered
    assert f"EnvironmentFile={RENDER_DIR}/.env" in rendered


def test_oneshot_units_are_root_jobs_without_install() -> None:
    ingest = _read("bcra-rag-ingest.service")
    refresh = _read("bcra-rag-refresh.service")
    for text, helper in (
        (ingest, "deploy/ingest.sh"),
        (refresh, "deploy/refresh.sh"),
    ):
        assert "Type=oneshot" in text
        assert "TimeoutStartSec=infinity" in text
        assert "[Install]" not in text
        assert "User=" not in text
        assert f"ExecStart={PLACEHOLDER_DIR}/{helper}" in text
        rendered = _render(text)
        assert f"ExecStart={RENDER_DIR}/{helper}" in rendered
        assert "User=" not in rendered


def test_job_helpers_flock_trap_cd_and_absolute_venv() -> None:
    ingest = _read("ingest.sh")
    refresh = _read("refresh.sh")
    for text, module in (
        (ingest, "bcra_rag.jobs.ingest"),
        (refresh, "bcra_rag.jobs.refresh"),
    ):
        assert "#!/bin/bash" in text
        assert "flock" in text
        assert "/run/bcra-rag-job.lock" in text
        assert "-n" not in text.split("flock", 1)[1].splitlines()[0]
        assert "trap" in text
        assert "systemctl start bcra-rag" in text
        assert "systemctl stop bcra-rag" in text
        assert f"cd {PLACEHOLDER_DIR}" in text
        assert f"sudo -u {PLACEHOLDER_USER}" in text
        assert f"{PLACEHOLDER_DIR}/.venv/bin/python -m " + module in text
        assert text.index("flock") < text.index("trap")
        assert text.index("trap") < text.index("systemctl stop")
        assert text.index("systemctl stop") < text.index(f"cd {PLACEHOLDER_DIR}")
        assert text.index(f"cd {PLACEHOLDER_DIR}") < text.index(
            f"{PLACEHOLDER_DIR}/.venv/bin/python"
        )
        rendered = _render(text)
        assert f"cd {RENDER_DIR}" in rendered
        assert f"sudo -u {RENDER_USER}" in rendered
        assert f"{RENDER_DIR}/.venv/bin/python -m " + module in rendered
        assert rendered.index("flock") < rendered.index("trap")
        assert rendered.index("trap") < rendered.index("systemctl stop")
        assert rendered.index("systemctl stop") < rendered.index(f"cd {RENDER_DIR}")
        assert rendered.index(f"cd {RENDER_DIR}") < rendered.index(
            f"{RENDER_DIR}/.venv/bin/python"
        )


def test_refresh_cron_is_cron_d_not_a_timer() -> None:
    text = _read("bcra-rag-refresh.cron")
    assert "0 6 * * * root systemctl start bcra-rag-refresh.service" in text
    assert ".timer" not in text
    assert "OnCalendar" not in text
    assert text.endswith("\n")


def test_deploy_script_requires_host_excludes_uv_restart_and_ingest_flag() -> None:
    text = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")
    assert "DEPLOY_HOST is required" in text
    assert "deploy/local.env" in text
    assert "content" + "labstudy" not in text
    assert "chita" + "-ts" not in text
    assert "/home/" + "redirect" not in text
    for exclude in (
        ".git/",
        ".venv/",
        "data/",
        "__pycache__/",
        ".env",
        ".envrc",
        "deploy/local.env",
        "coverage.xml",
        ".coverage",
    ):
        assert exclude in text
    assert "--delete-excluded" not in text
    assert "$HOME/.local/bin/uv" in text
    assert "uv sync --frozen --no-dev" in text
    assert "daemon-reload" in text
    assert "systemctl enable" in text
    assert "systemctl restart" in text
    assert "env.remote.example" in text
    assert "LLM_API_KEY" in text
    assert "EMBEDDING_API_KEY" in text
    assert "skip enable/restart when keys empty" in text
    assert "[ ! -f " in text or "[ ! -f" in text
    assert "--ingest" in text
    assert "systemctl start bcra-rag-ingest" in text
    assert "python -m bcra_rag.jobs.ingest" not in text
    assert "swapfile" not in text
    assert "fstab" not in text
    assert "2G" not in text
    assert "poppler-utils" in text
    assert "__DEPLOY_DIR__" in text
    assert "__DEPLOY_USER__" in text
    assert 'printf %s "$HOME/bcra-mini-rag"' in text
    assert "DEPLOY_USER is required when DEPLOY_HOST has no user@" in text


def test_remote_env_seed_uses_loopback_embeddings_and_grok() -> None:
    text = _read("env.remote.example")
    assert "EMBEDDING_BASE_URL=http://127.0.0.1:8001/v1" in text
    assert "EMBEDDING_MODEL=qwen3-embedding-0.6b" in text
    assert "EMBEDDING_API_KEY=sk-local" in text
    assert "EMBEDDING_MAX_CHARS=2048" in text
    assert "LLM_BASE_URL=https://api.x.ai/v1" in text
    assert "LLM_MODEL=grok-4-1-fast" in text
    assert "DATA_DIR=data" in text
    assert "export" not in text
    lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in text.splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    assert lines["LLM_API_KEY"] == ""


def test_local_env_example_has_no_real_hosts() -> None:
    text = _read("local.env.example")
    assert "deploy/local.env" in text
    assert "DEPLOY_HOST=user@your-dump-host" in text
    assert "content" + "labstudy" not in text
    assert "chita" + "-ts" not in text


def test_extra_env_keys_do_not_break_load(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TOTALLY_UNKNOWN_KEY", "should-be-ignored")
    monkeypatch.setenv("EMBEDDING_MODEL", "fake-embed")
    settings = Settings()
    assert settings.data_dir == tmp_path
    assert settings.embedding_model == "fake-embed"
