from __future__ import annotations

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_dotenv() -> None:
    # Local-first: load .env if present; CI/prod can rely on real env vars.
    load_dotenv(override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        frozen=True,
    )

    app_env: Literal["local", "dev", "prod"] = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    tz: str = Field(default="UTC", alias="TZ")
    schedule_every_hours: int = Field(default=4, alias="SCHEDULE_EVERY_HOURS")

    bot_token: str = Field(default="__MISSING__", alias="BOT_TOKEN")
    channel_id: str = Field(default="__MISSING__", alias="CHANNEL_ID")  # @channel_username or -100...
    dry_run: bool = Field(default=True, alias="DRY_RUN")

    openrouter_api_key: str = Field(default="__MISSING__", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    openrouter_model: str = Field(default="anthropic/claude-3.7-sonnet", alias="OPENROUTER_MODEL")

    sqlite_path: Path = Field(default=Path("./data/app.sqlite3"), alias="SQLITE_PATH")
    sources_config_path: Path = Field(default=Path("./sources.yaml"), alias="SOURCES_CONFIG_PATH")


def load_settings() -> Settings:
    _load_dotenv()
    return Settings()

