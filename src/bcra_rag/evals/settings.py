from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class EvalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    evals_dir: Path = Path("evals")
    judge_model: str = "grok-4.3"
    judge_base_url: str = "https://api.x.ai/v1"
    judge_api_key: str = ""
    judge_reasoning_effort: str = "none"
    llm_api_key: str = ""
    phoenix_collector_endpoint: str = ""
    phoenix_project_name: str = "bcra-rag"
    phoenix_api_key: str = ""

    def resolved_judge_key(self) -> str:
        return (self.judge_api_key or self.llm_api_key).strip()
