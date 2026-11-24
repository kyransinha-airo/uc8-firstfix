"""Settings from environment variables and backend/.env."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FirstFix"
    app_version: str = "0.1.0"
    environment: str = "local"

    # PostgreSQL. Unset: database features are skipped (offline tests still run).
    database_url: str | None = None
    # Tests only: admin URL used to create a throwaway database per test. Unset: DB tests skip.
    test_admin_url: str | None = None

    # LLM for the agent nodes (Azure OpenAI / Foundry)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str | None = None
    # None: send no temperature (reasoning deployments accept only their default).
    azure_openai_temperature: float | None = Field(default=None, ge=0, le=2)
    azure_openai_timeout_s: float = Field(default=60.0, gt=0)
    azure_openai_max_retries: int = Field(default=2, ge=0)

    # How agent and model calls run (app/core/model_calls.py):
    #   live   call the model
    #   record call the model for inputs not yet saved, and save outputs under replay_dir
    #   replay use only saved outputs; no model needed (demo, CI)
    llm_mode: Literal["live", "record", "replay"] = "live"
    replay_dir: Path = Path("../data/replay")

    # Local file storage (mock data, uploads). Relative paths are relative to backend/.
    data_dir: Path = Path("../data")

    cors_origins: str = "http://localhost:3008,http://127.0.0.1:3008"

    @field_validator("data_dir", "replay_dir")
    @classmethod
    def _relative_to_backend(cls, v: Path) -> Path:
        return v if v.is_absolute() else (_BACKEND_DIR / v).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
