"""Application configuration."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENVIRONMENT = os.getenv("ENVIRONMENT", "local")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    telegram_bot_token: str
    supabase_url: str
    supabase_service_key: str
    admin_token: str
    openai_api_key: str
    openai_model: str = "gpt-5.2"
    openai_reasoning_effort: str = "high"
    openai_store: bool = False
    fdc_api_key: str
    fdc_base_url: str = "https://api.nal.usda.gov/fdc/v1"
    environment: str = _ENVIRONMENT

    model_config = SettingsConfigDict(
        env_file=(f".env.{_ENVIRONMENT}", ".env"),
        extra="ignore",
    )
