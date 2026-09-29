from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.config import Settings, get_settings
from backend.app.db.base import Base
from backend.app.db.session import configure_sqlite_pragmas, get_db
from backend.app.main import create_app

# Test database: use a test SQLite database
TEST_DB_URL = "sqlite+aiosqlite:///storage/test_niko.db"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    settings = get_settings()
    settings.DATABASE_URL = TEST_DB_URL
    settings.SETUP_TOKEN = "test_setup_token_12345"
    settings.ENCRYPTION_KEY = (
        "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="  # Valid 32-byte Fernet base64 key
    )
    settings.TRUSTED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
    settings.WS_ALLOWED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
    settings.ensure_directories()
    return settings


@pytest.fixture(scope="session")
async def test_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(test_settings.DATABASE_URL, future=True)
    configure_sqlite_pragmas(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


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
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
