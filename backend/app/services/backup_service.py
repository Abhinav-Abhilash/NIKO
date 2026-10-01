import contextlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class BackupIntegrityError(Exception):
    """Raised when a created database backup fails SQLite integrity check."""
    pass


class BackupService:
    """
    Automated SQLite WAL backup manager.
    Safely takes online database snapshots using SQLite's online backup API,
    verifies page integrity, and manages retention pruning.
    """

    def __init__(self, db_path: Path | None = None, backup_dir: Path | None = None) -> None:
        settings = get_settings()
        self.db_path = (db_path or settings.resolve_db_path()).resolve()
        self.backup_dir = (backup_dir or (settings.get_storage_path() / "backups")).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, max_backups: int = 7) -> dict[str, Any]:
        """
        Execute an online snapshot backup of the live SQLite database.
        Locks are avoided using SQLite's non-blocking backup API.
        Integrity is verified with PRAGMA integrity_check before registering.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Source database file not found at: {self.db_path}")

        now = datetime.now(UTC)
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"niko_backup_{timestamp_str}.db"
        dest_path = (self.backup_dir / backup_filename).resolve()


        # Enforce destination is strictly inside backup_dir
        if not dest_path.is_relative_to(self.backup_dir):
            raise ValueError(f"Unsafe destination path: {dest_path}")

        logger.info("Starting online backup from %s to %s", self.db_path, dest_path)

        # Connect to source in read-only URI mode to guarantee zero write contention
        source_uri = f"file:{self.db_path.as_posix()}?mode=ro"
        try:
            src_conn = sqlite3.connect(source_uri, uri=True, timeout=10.0)
            dst_conn = sqlite3.connect(dest_path.as_posix())
            try:
                src_conn.backup(dst_conn, pages=100, sleep=0.005)
            finally:
                dst_conn.close()
                src_conn.close()

            # Verify integrity of the snapshot
            test_conn = sqlite3.connect(dest_path.as_posix())
            try:
                cursor = test_conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()
                if not result or result[0] != "ok":
                    raise BackupIntegrityError(f"Backup integrity check failed: {result}")
            finally:
                test_conn.close()


            size_bytes = dest_path.stat().st_size
            logger.info("Backup successfully completed: %s (%d bytes)", backup_filename, size_bytes)

            # Prune older backups
            pruned = self.prune_backups(max_backups=max_backups)

            return {
                "filename": backup_filename,
                "path": str(dest_path),
                "size_bytes": size_bytes,
                "created_at": now.isoformat(),
                "verified": True,
                "pruned_count": len(pruned),
            }

        except Exception as e:
            if dest_path.exists():
                with contextlib.suppress(OSError):
                    dest_path.unlink()
            logger.error("Failed to create SQLite backup: %s", e)
            raise

    def list_backups(self) -> list[dict[str, Any]]:
        """List all available SQLite backups sorted by creation time descending."""
        if not self.backup_dir.exists():
            return []

        backups = []
        for file in self.backup_dir.glob("niko_backup_*.db"):
            if file.is_file():
                stat = file.stat()
                created_dt = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                backups.append({
                    "filename": file.name,
                    "path": str(file.resolve()),
                    "size_bytes": stat.st_size,
                    "created_at": created_dt.isoformat(),
                })


        # Sort newest first
        backups.sort(key=lambda b: str(b["created_at"]), reverse=True)
        return backups


    def prune_backups(self, max_backups: int = 7) -> list[Path]:
        """Prune backups exceeding the retention threshold."""
        backups = [f for f in self.backup_dir.glob("niko_backup_*.db") if f.is_file()]
        # Sort newest first
        backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        pruned: list[Path] = []
        if len(backups) > max_backups:
            for excess in backups[max_backups:]:
                try:
                    excess.unlink()
                    pruned.append(excess)
                    logger.info("Pruned old backup: %s", excess.name)
                except OSError as e:
                    logger.warning("Could not prune backup %s: %s", excess.name, e)

        return pruned

    def delete_backup(self, filename: str) -> bool:
        """Delete a single backup by filename with path traversal defense."""
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValueError(f"Invalid backup filename: {filename}")

        target_path = (self.backup_dir / filename).resolve()
        if not target_path.is_relative_to(self.backup_dir):
            raise ValueError(f"Path traversal detected: {filename}")

        if not target_path.exists() or not target_path.is_file():
            return False

        target_path.unlink()
        logger.info("Deleted backup: %s", filename)
        return True
