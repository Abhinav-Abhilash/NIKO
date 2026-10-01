import contextlib
import os
import tempfile
from collections.abc import AsyncGenerator

# Set safe test defaults before importing backend.app so tests run without .env
_test_db_file = os.path.join(tempfile.gettempdir(), "niko_test.db").replace("\\", "/")
TEST_DB_URL = f"sqlite+aiosqlite:///{_test_db_file}"

os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("ENCRYPTION_KEY", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("JWT_SECRET_KEY", "ci_test_jwt_secret_key_1234567890_abcdefghijklmnop")
os.environ.setdefault("SETUP_TOKEN", "test_setup_token_12345")
os.environ.setdefault("APP_ENV", "test")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from backend.app.config import Settings, get_settings
from backend.app.db.base import Base
from backend.app.db.session import configure_sqlite_pragmas, get_db
from backend.app.main import create_app


def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    """Strictly assert test suite runs on an isolated temp database and never touches storage/niko.db."""
    settings = get_settings()
    assert "storage/niko.db" not in settings.DATABASE_URL.replace("\\", "/"), (
        "CRITICAL ERROR: Test runner configured to target production storage/niko.db!"
    )


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    settings = get_settings()
    settings.DATABASE_URL = TEST_DB_URL
    settings.SETUP_TOKEN = "test_setup_token_12345"
    settings.ENCRYPTION_KEY = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="
    settings.TRUSTED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
    settings.WS_ALLOWED_ORIGINS = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:1420",
        "http://localhost:1420",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ]
    settings.ensure_directories()
    return settings


@pytest.fixture(scope="session")
async def test_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(test_settings.DATABASE_URL, future=True, poolclass=NullPool)
    configure_sqlite_pragmas(engine)
    from backend.app.db.models.memory import init_memory_fts5_schema

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(init_memory_fts5_schema)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db_tables(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    from sqlalchemy import text

    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
        with contextlib.suppress(Exception):
            await conn.execute(text("DELETE FROM memories_fts;"))
    yield


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def async_client(
    test_engine: AsyncEngine, test_settings: Settings
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Origin": "http://localhost:5173"},
    ) as client:
        yield client
