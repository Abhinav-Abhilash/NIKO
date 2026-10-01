import os
import time
from pathlib import Path

from backend.app.services.janitor_service import JanitorService


def test_cleanup_screenshots(tmp_path: Path) -> None:
    storage_dir = tmp_path / "storage"
    screenshots_dir = storage_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    old_shot = screenshots_dir / "screen_old.webp"
    new_shot = screenshots_dir / "screen_new.webp"

    old_shot.write_bytes(b"old screenshot content")
    new_shot.write_bytes(b"new screenshot content")

    # Set old_shot mtime to 10 days ago
    ten_days_ago = time.time() - (10 * 86400)
    os.utime(old_shot, (ten_days_ago, ten_days_ago))

    janitor = JanitorService(storage_dir=storage_dir, max_screenshot_days=7)
    purged = janitor.cleanup_screenshots()

    assert purged == 1
    assert not old_shot.exists()
    assert new_shot.exists()


def test_rotate_and_cap_logs(tmp_path: Path) -> None:
    storage_dir = tmp_path / "storage"
    logs_dir = storage_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create 3 log files of 20KB each (total 60KB)
    f1 = logs_dir / "app_1.log"
    f2 = logs_dir / "app_2.log"
    f3 = logs_dir / "app_3.log"

    f1.write_bytes(b"A" * 20480)
    f2.write_bytes(b"B" * 20480)
    f3.write_bytes(b"C" * 20480)

    # Order by mtime: f1 oldest, f2 middle, f3 newest
    now = time.time()
    os.utime(f1, (now - 300, now - 300))
    os.utime(f2, (now - 200, now - 200))
    os.utime(f3, (now - 100, now - 100))

    # Cap at 30KB: should prune f1 (20KB), leaving 40KB, so also prune f2, leaving f3 (20KB < 30KB)
    janitor = JanitorService(storage_dir=storage_dir, max_logs_size_bytes=30000)
    freed = janitor.rotate_and_cap_logs()

    assert freed == 40960
    assert not f1.exists()
    assert not f2.exists()
    assert f3.exists()


def test_storage_status_and_maintenance_cycle(tmp_path: Path) -> None:
    storage_dir = tmp_path / "storage"
    janitor = JanitorService(storage_dir=storage_dir)

    status = janitor.get_storage_status()
    assert "database" in status
    assert "backups" in status
    assert "screenshots" in status
    assert "logs" in status
    assert "total_storage_bytes" in status

    cycle_res = janitor.run_maintenance_cycle()
    assert cycle_res["status"] == "completed"
    assert "screenshots_purged" in cycle_res
    assert "log_bytes_freed" in cycle_res
    assert "backups_pruned" in cycle_res
