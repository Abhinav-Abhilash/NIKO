import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_empty_database_and_check_drift() -> None:
    """
    Test that an empty database upgrades cleanly to head via Alembic migrations,
    and that alembic check verifies zero schema drift between models and migrations.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        temp_db_path = Path(tmp_dir) / "test_migration.db"
        temp_db_url = f"sqlite:///{temp_db_path.as_posix()}"

        root_dir = Path(__file__).resolve().parent.parent.parent
        ini_path = root_dir / "alembic.ini"

        alembic_cfg = Config(str(ini_path))
        alembic_cfg.set_main_option("script_location", str(root_dir / "backend" / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", temp_db_url)

        # 1. Upgrade from clean empty database to head
        command.upgrade(alembic_cfg, "head")

        # 2. Assert all expected tables were created solely via migrations
        engine = create_engine(temp_db_url)
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
        command.check(alembic_cfg)
