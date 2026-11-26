"""Settings, read from the .env file in the project root.

Secrets (passwords, keys) live only in .env, which is never committed.
.env.example lists the names with placeholder values.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # extra="ignore": .env also holds values for other parts of the project.
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    database_url: str
    # Separate database for pytest, so tests never touch the development data.
    test_database_url: str | None = None


settings = Settings()
