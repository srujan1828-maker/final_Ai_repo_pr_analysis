"""
Central settings object. Everything environment-specific lives here so
no other module reads os.environ directly.
"""
import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env/local",
        env_file_encoding="utf-8",
        extra="ignore",
        enable_decoding=False,
    )

    # --- App ---
    app_name: str = "ai-review-backend"
    environment: str = "development"
    debug: bool = True
    create_db_tables: bool = True

    # --- Database ---
    # postgresql+asyncpg://user:password@host:port/dbname
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_review"

    # --- GitHub (Stage 0 / Stage 6) ---
    github_webhook_secret: str = ""  # Must be set via GITHUB_WEBHOOK_SECRET env var
    github_token: str = ""  # PAT or GitHub App installation token, used to post comments/checks

    # --- Sandbox service (Stage 2 / Stage 3) ---
    sandbox_base_url: str = "http://localhost:9000"
    sandbox_timeout_seconds: int = 130  # slightly above the 120s job timeout so we don't cut it off early

    # --- AI engine (Stage 4 / Stage 5) ---
    ai_engine_base_url: str = "http://localhost:9100"
    ai_engine_timeout_seconds: int = 35  # 30s LLM call + buffer, per the schema doc

    # --- CORS (frontend dev server) ---
    cors_origins_raw: str | list[str] = Field(
        default="http://localhost:3000,http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )
    cors_origin_regex: str = Field(default="", validation_alias="CORS_ORIGIN_REGEX")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Accept Render's postgres:// URLs while keeping SQLAlchemy async."""
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+asyncpg://", 1)
            if value.startswith("postgresql://") and "+" not in value.split("://", 1)[0]:
                return value.replace("postgresql://", "postgresql+asyncpg://", 1)
            if value.startswith("postgresql+psycopg2://"):
                return value.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
            if value.startswith("postgresql+psycopg://"):
                return value.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("cors_origins_raw", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> str | list[str]:
        """Allow CORS_ORIGINS as JSON or a comma-separated Render env var."""
        if isinstance(value, list):
            return ",".join(value)
        if isinstance(value, str):
            stripped_value = value.strip()
            if stripped_value.startswith("["):
                return json.loads(stripped_value)
            return stripped_value
        return value

    @property
    def cors_origins(self) -> list[str]:
        """Return CORS origins from either JSON/list or comma-separated env vars."""
        if isinstance(self.cors_origins_raw, str):
            return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]
        return self.cors_origins_raw

    @property
    def should_create_db_tables(self) -> bool:
        """Create tables automatically in dev, or explicitly on first cloud deploy."""
        return self.environment == "development" or self.create_db_tables

    @property
    def sync_database_url(self) -> str:
        """Alembic migrations use the sync psycopg driver, not asyncpg."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
