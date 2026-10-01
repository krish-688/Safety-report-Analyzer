from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", str(BACKEND_DIR / ".env")), extra="ignore"
    )

    APP_NAME: str = "Safety Incident Analysis"
    API_PREFIX: str = "/api/v1"

    # Change only this string to move to PostgreSQL / MySQL.
    DATABASE_URL: str = "sqlite:///./safety.db"

    SECRET_KEY: str = "dev-only-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    UPLOAD_DIR: str = str(BACKEND_DIR / "uploads")
    MAX_UPLOAD_MB: int = 10
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".csv"]

    CORS_ORIGINS: list[str] = ["http://localhost:8501"]

    SEED_ADMIN_EMAIL: str = "admin@safety.local"
    SEED_ADMIN_PASSWORD: str = "Admin@12345"
    SEED_DEMO_PASSWORD: str = "Demo@12345"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
