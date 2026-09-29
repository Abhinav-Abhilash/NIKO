from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.config import get_settings


def configure_sqlite_pragmas(engine: AsyncEngine | Engine) -> None:
    """Register PRAGMAs: foreign_keys=ON, journal_mode=WAL, busy_timeout=5000ms."""
    target_engine = engine.sync_engine if isinstance(engine, AsyncEngine) else engine

    @event.listens_for(target_engine, "connect")
    def set_pragmas(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()


def create_engine_and_sessionmaker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    settings = get_settings()
    settings.ensure_directories()

    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
    )
    configure_sqlite_pragmas(engine)

    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return engine, session_maker


# Internal singleton instances
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_maker
    if _engine is None:
        _engine, _session_maker = create_engine_and_sessionmaker()
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_maker
    if _session_maker is None:
        _engine, _session_maker = create_engine_and_sessionmaker()
    return _session_maker


def __getattr__(name: str) -> Any:
    """Allow backward-compatible module-level access to engine and async_session_maker lazily."""
    if name == "engine":
        return get_engine()
    if name == "async_session_maker":
        return get_session_maker()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing an async database session per request."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
