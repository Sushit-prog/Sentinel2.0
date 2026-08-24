"""Central configuration. Every runtime setting flows through Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SENTINEL_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_SENTINEL_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    log_json: bool = False

    groq_api_key: SecretStr

    llm_strong_model: str = "llama-3.3-70b-versatile"
    llm_fast_model: str = "llama-3.1-8b-instant"
    llm_router_default: Literal["auto", "fast", "strong"] = "auto"
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 2
    llm_verification_samples: int = 3
    daily_token_budget: int = 12000

    database_url: str = f"sqlite:///{_SENTINEL_DIR / 'data' / 'sentinel.db'}"
    chroma_persist_dir: str = str(_SENTINEL_DIR / "data" / "chromadb")
    reports_dir: str = str(_SENTINEL_DIR / "reports")

    neo4j_uri: Optional[str] = None
    neo4j_username: Optional[str] = None
    neo4j_password: SecretStr | None = None

    api_keys: str = ""
    rate_limit_per_minute: int = 60
    cors_origins: str = "http://localhost:8501"

    @model_validator(mode="after")
    def _enforce_production_basics(self) -> "Settings":
        if self.app_env == "production":
            if not self.api_keys.strip():
                raise ValueError("api_keys must be set when app_env=production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("sqlite is not a supported production database")
        return self

    @property
    def api_key_set(self) -> frozenset[str]:
        return frozenset(k.strip() for k in self.api_keys.split(",") if k.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
