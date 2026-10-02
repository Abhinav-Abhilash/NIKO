import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_empty_database_and_check_drift() -> None:
    """
    Test that an empty database upgrades cleanly to head via Alembic migrations,
    and that alembic check verifies zero schema drift between models and migrations.
    Uses an isolated subprocess to prevent pytest asyncio event loop interference.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        temp_db_path = Path(tmp_dir) / "test_migration.db"
        temp_sqlite_url = f"sqlite:///{temp_db_path.as_posix()}"

        root_dir = Path(__file__).resolve().parent.parent.parent
        alembic_exe = Path(sys.executable).parent / ("alembic.exe" if sys.platform == "win32" else "alembic")
        exe_path = str(alembic_exe) if alembic_exe.exists() else "alembic"

        env = dict(os.environ)
        env["DATABASE_URL"] = f"sqlite+aiosqlite:///{temp_db_path.as_posix()}"
        env["PYTHONPATH"] = str(root_dir)

        # 1. Upgrade from clean empty database to head
        res_upgrade = subprocess.run(
            [exe_path, "-x", f"db_url={temp_sqlite_url}", "upgrade", "head"],
            cwd=str(root_dir),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_upgrade.returncode == 0, f"Alembic upgrade failed:\n{res_upgrade.stderr}\n{res_upgrade.stdout}"

        # 2. Assert all expected tables were created solely via migrations
        engine = create_engine(temp_sqlite_url)
        try:
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())

            expected_tables = {
                "users",
                "sessions",
                "conversations",
                "messages",
                "reminders",
                "scheduled_tasks",
                "llm_providers",
                "settings",
                "command_logs",
                "approvals",
                "memories",
                "documents",
                "document_chunks",
                "notes",
                "alembic_version",
            }

            assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"
        finally:
            engine.dispose()

        # 3. Assert zero schema drift
        res_check = subprocess.run(
            [exe_path, "-x", f"db_url={temp_sqlite_url}", "check"],
            cwd=str(root_dir),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_check.returncode == 0, f"Alembic check failed:\n{res_check.stderr}\n{res_check.stdout}"
