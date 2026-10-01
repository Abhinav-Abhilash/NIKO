import sqlite3
from pathlib import Path

import pytest

from backend.app.services.backup_service import BackupService


@pytest.fixture
def test_db_and_backup_dir(tmp_path: Path) -> tuple[Path, Path]:
    db_file = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"

    # Populate a source sqlite database with WAL mode
    with sqlite3.connect(db_file.as_posix()) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
        conn.execute("INSERT INTO users (name) VALUES ('alice'), ('bob');")
        conn.commit()

    return db_file, backup_dir


def test_create_and_verify_backup(test_db_and_backup_dir: tuple[Path, Path]) -> None:
    db_file, backup_dir = test_db_and_backup_dir
    service = BackupService(db_path=db_file, backup_dir=backup_dir)

    result = service.create_backup(max_backups=5)

    assert result["verified"] is True
    assert result["size_bytes"] > 0
    backup_file = Path(str(result["path"]))
    assert backup_file.exists()

    # Validate snapshot integrity and data contents
    bconn = sqlite3.connect(backup_file.as_posix())
    try:
        cursor = bconn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()
        assert res is not None
        assert res[0] == "ok"

        cursor.execute("SELECT name FROM users ORDER BY id;")
        rows = cursor.fetchall()
        assert [r[0] for r in rows] == ["alice", "bob"]
    finally:
        bconn.close()



def test_backup_pruning(test_db_and_backup_dir: tuple[Path, Path]) -> None:
    db_file, backup_dir = test_db_and_backup_dir
    service = BackupService(db_path=db_file, backup_dir=backup_dir)

    # Create 4 mock backups
    for i in range(4):
        f = backup_dir / f"niko_backup_2026100{i}_000000.db"
        f.write_text("mock content")

    backups = service.list_backups()
    assert len(backups) == 4

    pruned = service.prune_backups(max_backups=2)
    assert len(pruned) == 2

    remaining = service.list_backups()
    assert len(remaining) == 2


def test_backup_delete_and_path_traversal(test_db_and_backup_dir: tuple[Path, Path]) -> None:
    db_file, backup_dir = test_db_and_backup_dir
    service = BackupService(db_path=db_file, backup_dir=backup_dir)

    result = service.create_backup()
    filename = str(result["filename"])

    # Delete valid
    assert service.delete_backup(filename) is True
    assert service.delete_backup(filename) is False

    # Path traversal attempts
    with pytest.raises(ValueError, match="Invalid backup filename"):
        service.delete_backup("../escape.db")

    with pytest.raises(ValueError, match="Invalid backup filename"):
        service.delete_backup("sub/escape.db")


def test_backup_nonexistent_source(tmp_path: Path) -> None:
    nonexistent = tmp_path / "missing.db"
    backup_dir = tmp_path / "backups"
    service = BackupService(db_path=nonexistent, backup_dir=backup_dir)

    with pytest.raises(FileNotFoundError):
        service.create_backup()
