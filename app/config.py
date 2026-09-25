"""Điểm đọc cấu hình DUY NHẤT của ứng dụng. Mọi secret đi qua đây."""
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Notion
    notion_token: str = ""
    notion_database_id: str = ""
    notion_version: str = "2022-06-28"

    # Discord
    discord_bot_token: str = ""
    discord_guild_id: str = ""

    # LLM
    llm_provider: str = "glm"  # glm | ollama
    llm_api_key: str = ""
    llm_model: str = "glm-4-flash"
    ollama_base_url: str = "http://localhost:11434"
    openai_base_url: str = "https://api.openai.com/v1"

    # Email
    email_backend: str = "smtp"  # smtp | resend
    email_from: str = "SEE Notion Bot <bot@example.com>"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    resend_api_key: str = ""

    # App
    app_token: str = "dev-token"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    tz_config: str = "Asia/Ho_Chi_Minh"
    log_level: str = "INFO"

    @property
    def business_tz(self):
        from zoneinfo import ZoneInfo
        return ZoneInfo(self.tz_config)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_yaml_config(path: Path | None = None) -> dict:
    """config.yaml — cấu hình nghiệp vụ (không chứa secret)."""
    path = path or BASE_DIR / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_team(path: Path | None = None) -> list[dict]:
    path = path or BASE_DIR / "team.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f).get("users", [])
