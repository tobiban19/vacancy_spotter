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
    jwt_secret: SecretStr = SecretStr("saas_secret_key_change_me_in_production")
    demo_duration_days: int = 2
    telegram_proxy: str | None = None
    admin_chat_id: int = 965000782
    admin_telegram_ids_raw: str = Field(default="", validation_alias="ADMIN_TELEGRAM_IDS")

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
