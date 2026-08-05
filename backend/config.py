"""
Configuration settings for Vacancy Spotter SaaS backend.
"""

from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    bot_token: SecretStr = SecretStr("placeholder_token")
    database_url: str = "sqlite+aiosqlite:///../data/saas_spotter.sqlite3"
    jwt_secret: SecretStr = SecretStr("saas_secret_key_change_me_in_production_min_32_bytes_long")
    jwt_expire_hours: int = 24 * 7
    demo_duration_days: int = 2
    telegram_proxy: str | None = None
    admin_chat_id: int = 965000782
    admin_telegram_ids_raw: str = Field(default="", validation_alias="ADMIN_TELEGRAM_IDS")
    telegram_api_id: int = 0
    telegram_api_hash: SecretStr = SecretStr("")
    # Comma-separated list of allowed origins for CORS (Mini App domains).
    # Falls back to permissive mode only when explicitly set to "*".
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")
    # Optional shared secret required by the internal /api/jobs/incoming webhook.
    # When set, callers must pass header "X-Webhook-Secret" with the same value.
    jobs_webhook_secret: SecretStr = SecretStr("")
    # OpenRouter (LLM) settings for AI-generated draft replies.
    # When OPENROUTER_API_KEY is empty/unset, generation gracefully falls back
    # to the local template-based reply (no network call).
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-2.5-flash-lite"
    openrouter_timeout_seconds: float = 20.0

    @property
    def cors_origins_list(self) -> list[str] | None:
        """Returns the allowed CORS origins, or None to allow all (dev only)."""
        raw = self.cors_origins.strip()
        if not raw:
            return None
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def admin_telegram_ids(self) -> list[int]:
        ids = [self.admin_chat_id, 965000782]
        if self.admin_telegram_ids_raw:
            for x in self.admin_telegram_ids_raw.split(","):
                if x.strip().isdigit():
                    ids.append(int(x.strip()))
        return list(set(ids))

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
