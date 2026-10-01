import contextlib
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.config import get_settings
from backend.app.services.backup_service import BackupService

logger = logging.getLogger(__name__)


class JanitorService:
    """
    Storage maintenance and retention janitor.
    - Purges screenshot files older than 7 days.
    - Caps and manages structured log sizes at 50MB.
    - Coordinates backup retention and computes global storage metrics.
    """

    def __init__(
        self,
        storage_dir: Path | None = None,
        max_screenshot_days: int = 7,
        max_logs_size_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        settings = get_settings()
        self.storage_dir = (storage_dir or settings.get_storage_path()).resolve()
        self.screenshots_dir = (self.storage_dir / "screenshots").resolve()
        self.logs_dir = (self.storage_dir / "logs").resolve()
        self.backups_dir = (self.storage_dir / "backups").resolve()
        self.db_path = settings.resolve_db_path()

        self.max_screenshot_days = max_screenshot_days
        self.max_logs_size_bytes = max_logs_size_bytes

        # Ensure directories exist
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_screenshots(self, max_age_days: int | None = None) -> int:
        """
        Purge screenshots older than max_age_days (default 7 days).
        Includes strict path validation against directory traversal.
        """
        days = max_age_days if max_age_days is not None else self.max_screenshot_days
        now_ts = datetime.now(UTC).timestamp()
        cutoff_ts = now_ts - (days * 86400)


        purged_count = 0
        if not self.screenshots_dir.exists():
            return 0

        for root, _, files in os.walk(self.screenshots_dir):
            root_path = Path(root).resolve()
            if not root_path.is_relative_to(self.screenshots_dir):
                continue

            for fname in files:
                file_path = (root_path / fname).resolve()
                if not file_path.is_relative_to(self.screenshots_dir):
                    continue

                try:
                    stat = file_path.stat()
                    if stat.st_mtime < cutoff_ts:
                        file_path.unlink()
                        purged_count += 1
                        logger.info("Janitor purged old screenshot: %s", fname)
                except OSError as e:
                    logger.warning("Janitor failed to unlink screenshot %s: %s", fname, e)

        return purged_count

    def rotate_and_cap_logs(self, max_bytes: int | None = None) -> int:
        """
        Enforce structured log directory cap (default 50MB).
        If total log size exceeds cap, oldest log files are pruned.
        """
        cap = max_bytes if max_bytes is not None else self.max_logs_size_bytes
        if not self.logs_dir.exists():
            return 0

        log_files: list[Path] = []
        for file in self.logs_dir.glob("*.log*"):
            if file.is_file() and file.resolve().is_relative_to(self.logs_dir):
                log_files.append(file)

        # Sort by mtime ascending (oldest first)
        log_files.sort(key=lambda f: f.stat().st_mtime)

        total_size = sum(f.stat().st_size for f in log_files)
        bytes_freed = 0

        while total_size > cap and log_files:
            oldest = log_files.pop(0)
            try:
                sz = oldest.stat().st_size
                oldest.unlink()
                total_size -= sz
                bytes_freed += sz
                logger.info("Janitor rotated/pruned log file: %s (%d bytes)", oldest.name, sz)
            except OSError as e:
                logger.warning("Could not prune log file %s: %s", oldest.name, e)

        return bytes_freed

    def run_maintenance_cycle(self) -> dict[str, Any]:
        """Execute a full maintenance sweep: screenshots, logs, and backups."""
        screenshots_purged = self.cleanup_screenshots()
        log_bytes_freed = self.rotate_and_cap_logs()

        backup_service = BackupService(db_path=self.db_path, backup_dir=self.backups_dir)
        pruned_backups = backup_service.prune_backups(max_backups=7)

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "screenshots_purged": screenshots_purged,
            "log_bytes_freed": log_bytes_freed,
            "backups_pruned": len(pruned_backups),
            "status": "completed",
        }

    def get_storage_status(self) -> dict[str, Any]:
        """Compute disk usage metrics across storage modules."""
        def dir_stats(p: Path) -> tuple[int, int]:
            count = 0
            size = 0
            if p.exists():
                for f in p.rglob("*"):
                    if f.is_file():
                        count += 1
                        with contextlib.suppress(OSError):
                            size += f.stat().st_size
            return count, size

        screenshots_count, screenshots_size = dir_stats(self.screenshots_dir)
        logs_count, logs_size = dir_stats(self.logs_dir)
        backups_count, backups_size = dir_stats(self.backups_dir)

        db_size = 0
        if self.db_path.exists():
            with contextlib.suppress(OSError):
                db_size = self.db_path.stat().st_size


        total_storage = db_size + screenshots_size + logs_size + backups_size

        return {
            "database": {
                "path": str(self.db_path),
                "size_bytes": db_size,
            },
            "backups": {
                "count": backups_count,
                "size_bytes": backups_size,
            },
            "screenshots": {
                "count": screenshots_count,
                "size_bytes": screenshots_size,
            },
            "logs": {
                "count": logs_count,
                "size_bytes": logs_size,
                "cap_bytes": self.max_logs_size_bytes,
            },
            "total_storage_bytes": total_storage,
        }
