"""Application settings, read from environment variables or a local .env file."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROAMWISE_", env_file=".env", extra="ignore")

    # Which model backend the agents use. "mock" is rule-based and needs no key.
    llm_provider: Literal["mock", "anthropic", "bedrock"] = "mock"
    llm_model: str = "claude-opus-5-5"
    aws_region: str = "us-east-1"

    db_path: str = "roamwise.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # How many times the critic may send a plan back to the planner.
    max_revisions: int = 2
    http_timeout_seconds: float = 20.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
