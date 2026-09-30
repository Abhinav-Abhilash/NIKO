import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet


def generate_env() -> None:
    env_path = Path(".env")
    if env_path.exists():
        print(".env already exists, keeping existing file.")
        return

    fernet_key = Fernet.generate_key().decode()
    jwt_secret = secrets.token_urlsafe(32)
    setup_token = secrets.token_hex(24)

    gemini_key = os.environ.get("INITIAL_GEMINI_API_KEY", "")
    groq_key = os.environ.get("INITIAL_GROQ_API_KEY", "")
    openrouter_key = os.environ.get("INITIAL_OPENROUTER_API_KEY", "")

    lines = [
        "# Auto-generated NIKO Environment Configuration",
        "APP_ENV=development",
        "APP_NAME=NIKO",
        "HOST=127.0.0.1",
        "PORT=8000",
        "DEBUG=false",
        "",
        "DATABASE_URL=sqlite+aiosqlite:///storage/niko.db",
        "",
        f"ENCRYPTION_KEY={fernet_key}",
        f"JWT_SECRET_KEY={jwt_secret}",
        "JWT_ALGORITHM=HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES=15",
        "REFRESH_TOKEN_EXPIRE_DAYS=7",
        "",
        f"SETUP_TOKEN={setup_token}",
        "",
        'TRUSTED_HOSTS=["127.0.0.1", "localhost", "testserver"]',
        'CORS_ORIGINS=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:1420", "http://localhost:1420", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]',
        'WS_ALLOWED_ORIGINS=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:1420", "http://localhost:1420", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]',
        "",
        "STORAGE_DIR=storage",
        "LOG_LEVEL=INFO",
        "",
        f"INITIAL_GEMINI_API_KEY={gemini_key}",
        f"INITIAL_GROQ_API_KEY={groq_key}",
        f"INITIAL_OPENROUTER_API_KEY={openrouter_key}",
    ]

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"SUCCESS: Created .env with SETUP_TOKEN={setup_token}")


if __name__ == "__main__":
    generate_env()
