"""
Configuration settings for Vacancy Spotter SaaS backend.
"""

from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    bot_token: SecretStr = SecretStr("placeholder_token")
    database_url: str = "sqlite+aiosqlite:///../data/saas_spotter.sqlite3"
    jwt_secret: SecretStr = SecretStr("saas_secret_key_change_me_in_production")
    demo_duration_days: int = 2
    telegram_proxy: str | None = None
    admin_telegram_ids_raw: str = ""

    @property
    def admin_telegram_ids(self) -> list[int]:
        if not self.admin_telegram_ids_raw:
            return []
        return [int(x.strip()) for x in self.admin_telegram_ids_raw.split(",") if x.strip().isdigit()]

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
