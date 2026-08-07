"""
Central settings object. Everything environment-specific lives here so
no other module reads os.environ directly.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "ai-review-backend"
    environment: str = "development"
    debug: bool = True

    # --- Database ---
    # postgresql+asyncpg://user:password@host:port/dbname
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_review"

    # --- GitHub (Stage 0 / Stage 6) ---
    github_webhook_secret: str = "change-me"
    github_token: str = ""  # PAT or GitHub App installation token, used to post comments/checks

    # --- Sandbox service (Stage 2 / Stage 3) ---
    sandbox_base_url: str = "http://localhost:9000"
    sandbox_timeout_seconds: int = 130  # slightly above the 120s job timeout so we don't cut it off early

    # --- AI engine (Stage 4 / Stage 5) ---
    ai_engine_base_url: str = "http://localhost:9100"
    ai_engine_timeout_seconds: int = 35  # 30s LLM call + buffer, per the schema doc

    # --- CORS (frontend dev server) ---
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @property
    def sync_database_url(self) -> str:
        """Alembic migrations use the sync psycopg driver, not asyncpg."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
