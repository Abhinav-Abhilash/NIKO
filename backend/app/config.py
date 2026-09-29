from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Settings
    APP_NAME: str = "NIKO"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False

    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///storage/niko.db"

    # Security Keys
    ENCRYPTION_KEY: str = Field(
        ...,
        description="Fernet symmetric encryption key for storing external secrets",
    )
    JWT_SECRET_KEY: str = Field(
        ...,
        description="Secret key for signing JWT access and refresh tokens",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # First Boot Setup Barrier
    SETUP_TOKEN: str = Field(
        ...,
        description="One-time cryptographically secure setup token required to create the first owner",
    )

    # Network Isolation
    TRUSTED_HOSTS: list[str] = ["127.0.0.1", "localhost", "testserver"]
    CORS_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    WS_ALLOWED_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    # Storage Paths & Retention
    STORAGE_DIR: Path = Path("storage")
    LOG_LEVEL: str = "INFO"

    # Initial Provider Keys (optional seed)
    INITIAL_GEMINI_API_KEY: str | None = None
    INITIAL_GROQ_API_KEY: str | None = None
    INITIAL_OPENROUTER_API_KEY: str | None = None

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("sqlite+aiosqlite:///"):
            return v
        return v

    def resolve_db_path(self) -> Path:
        """Extract the local filesystem path from sqlite+aiosqlite URI, handling spaces."""
        raw_path = self.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        return Path(raw_path).resolve()

    def get_storage_path(self) -> Path:
        return self.STORAGE_DIR.resolve()

    def ensure_directories(self) -> None:
        """Ensure necessary storage subdirectories exist."""
        storage_path = self.get_storage_path()
        storage_path.mkdir(parents=True, exist_ok=True)
        (storage_path / "screenshots").mkdir(parents=True, exist_ok=True)
        (storage_path / "logs").mkdir(parents=True, exist_ok=True)
        (storage_path / "backups").mkdir(parents=True, exist_ok=True)

        db_path = self.resolve_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)


# Lazy-loaded singleton or explicit factory
_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()  # type: ignore[call-arg]
    return _settings_instance
