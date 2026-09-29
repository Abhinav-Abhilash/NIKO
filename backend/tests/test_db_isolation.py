import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.models import User


def test_test_environment_never_targets_production_db() -> None:
    settings = get_settings()
    db_url = settings.DATABASE_URL.replace("\\", "/")

    # 1. Must never contain production storage/niko.db
    assert "storage/niko.db" not in db_url

    # 2. Must be located inside system temporary directory
    temp_dir = tempfile.gettempdir().replace("\\", "/").rstrip("/")
    assert temp_dir in db_url
    assert "niko_test.db" in db_url


@pytest.mark.asyncio
async def test_storage_niko_db_file_unmodified_during_test_execution(
    db_session: AsyncSession,
) -> None:
    prod_db_path = Path("storage/niko.db")
    prod_mtime_before = prod_db_path.stat().st_mtime if prod_db_path.exists() else None

    # Perform mutations on test db session
    test_user = User(username="isolation_check_user", password_hash="hash", role="owner")
    db_session.add(test_user)
    await db_session.commit()

    loaded = (
        await db_session.execute(
            select(User).where(User.username == "isolation_check_user")
        )
    ).scalar_one()
    assert loaded.id is not None

    # Verify production database was never modified
    if prod_db_path.exists():
        prod_mtime_after = prod_db_path.stat().st_mtime
        assert prod_mtime_before == prod_mtime_after, (
            "FATAL: storage/niko.db was modified during test suite execution!"
        )
