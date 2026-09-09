from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    data_dir: Path = Path("data")
    evals_dir: Path = Path("evals")

    # Embeddings (ingest / index)
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_backend: str = "auto"
    embedding_batch_size: int = Field(default=8, ge=1, le=256)
    embedding_timeout_s: float = Field(default=120.0, ge=1.0)
    embedding_max_chars: int = Field(default=2048, ge=256)

    # Chat LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://api.x.ai/v1"
    llm_model: str = "grok-4-1-fast"
    llm_timeout_s: float = Field(default=60.0, ge=1.0)
    llm_enable_thinking: bool = True
    demo_api_key: str = ""
    max_message_chars: int = Field(default=4000, ge=1)
    max_context_chars: int = Field(default=12000, ge=256)
    guardrails_policy_path: Path | None = None

    # Retrieval
    default_k: int = Field(default=5, ge=1)
    max_k: int = Field(default=8, ge=1)

    # Chat rate limit
    rate_limit_requests: int = Field(default=20, ge=1)
    rate_limit_window_s: int = Field(default=60, ge=1)
    chat_turns_per_email_day: int = Field(default=30, ge=1)
    chat_turns_per_process_day: int = Field(default=100, ge=1)

    # Corpus ingest
    download_concurrency: int = Field(default=3, ge=2, le=4)
    download_delay_s: float = Field(default=0.2, ge=0.0)
    user_agent: str = "BCRAMiniRag/0.1 (CAMEX corpus ingest)"

    @property
    def dump_dir(self) -> Path:
        return self.data_dir / "bcra" / "current"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def raw_dir(self) -> Path:
        return self.dump_dir / "raw"

    @property
    def extract_dir(self) -> Path:
        return self.dump_dir / "extract"

    @property
    def manifest_path(self) -> Path:
        return self.dump_dir / "MANIFEST.json"

    @property
    def notes_path(self) -> Path:
        return self.dump_dir / "NOTES.md"
