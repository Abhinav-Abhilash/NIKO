import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from backend.app.core.exceptions import NotFoundError
from backend.app.core.logging import get_logger

logger = get_logger("shadow_copy_service")

STAGING_DIR = Path("storage/undo_staging")


class ShadowCopyService:
    """
    Manages pre-mutation shadow copies of files in local staging storage.
    Enables instant, safe rollback of file automation actions ("undo that").
    """

    def __init__(self, staging_dir: Path = STAGING_DIR) -> None:
        self.staging_dir = staging_dir
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_file_hash(self, path: Path) -> str:
        """Calculate SHA-256 hash of a file for integrity verification."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_snapshot(
        self,
        file_paths: list[str | Path],
        description: str = "Automated file mutation snapshot",
    ) -> str:
        """
        Create a shadow copy snapshot of specified files before mutation.
        Returns the snapshot_id.
        """
        snapshot_id = f"snap_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        snapshot_folder = self.staging_dir / snapshot_id
        snapshot_folder.mkdir(parents=True, exist_ok=True)

        records = []
        for fp in file_paths:
            p = Path(fp).resolve()
            if not p.exists():
                records.append({
                    "original_path": str(p),
                    "existed_before": False,
                    "shadow_filename": None,
                    "sha256": None,
                    "size_bytes": 0,
                })
            else:
                shadow_name = f"{uuid.uuid4().hex}_{p.name}"
                dest = snapshot_folder / shadow_name
                if p.is_file():
                    shutil.copy2(p, dest)
                    records.append({
                        "original_path": str(p),
                        "existed_before": True,
                        "shadow_filename": shadow_name,
                        "sha256": self._calculate_file_hash(p),
                        "size_bytes": p.stat().st_size,
                    })

        manifest = {
            "snapshot_id": snapshot_id,
            "created_at": time.time(),
            "description": description,
            "files": records,
        }
        manifest_file = snapshot_folder / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        logger.info("Created undo shadow snapshot", snapshot_id=snapshot_id, files_count=len(records))
        return snapshot_id

    def restore_snapshot(self, snapshot_id: str | None = None) -> dict[str, Any]:
        """
        Restore files from snapshot back to original locations.
        If snapshot_id is None, reverts the most recent snapshot.
        """
        if not snapshot_id:
            all_snaps = self.list_snapshots()
            if not all_snaps:
                raise NotFoundError("No undo snapshots available to revert.")
            snapshot_id = all_snaps[0]["snapshot_id"]

        snapshot_folder = self.staging_dir / snapshot_id
        manifest_file = snapshot_folder / "manifest.json"
        if not manifest_file.exists():
            raise NotFoundError(f"Snapshot '{snapshot_id}' does not exist or manifest is missing.")

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        restored_files = []
        errors = []

        for item in manifest.get("files", []):
            orig_path = Path(item["original_path"])
            existed = item["existed_before"]
            shadow_name = item.get("shadow_filename")

            try:
                if not existed:
                    # File was newly created by the action; delete it on undo
                    if orig_path.exists():
                        if orig_path.is_file():
                            orig_path.unlink()
                        elif orig_path.is_dir():
                            shutil.rmtree(orig_path)
                    restored_files.append({"path": str(orig_path), "action": "removed_new_file"})
                else:
                    # Restore original content
                    if shadow_name:
                        src = snapshot_folder / shadow_name
                        if src.exists():
                            orig_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, orig_path)
                            restored_files.append({"path": str(orig_path), "action": "restored_original"})
            except Exception as exc:
                errors.append({"path": str(orig_path), "error": str(exc)})

        return {
            "snapshot_id": snapshot_id,
            "description": manifest.get("description"),
            "restored_count": len(restored_files),
            "restored_files": restored_files,
            "errors": errors,
            "success": len(errors) == 0,
        }

    def list_snapshots(self) -> list[dict[str, Any]]:
        """List all available undo snapshots sorted newest first."""
        if not self.staging_dir.exists():
            return []

        snapshots = []
        for folder in self.staging_dir.iterdir():
            if folder.is_dir():
                manifest_file = folder / "manifest.json"
                if manifest_file.exists():
                    try:
                        data = json.loads(manifest_file.read_text(encoding="utf-8"))
                        snapshots.append(data)
                    except Exception:
                        continue

        snapshots.sort(key=lambda s: s.get("created_at", 0), reverse=True)
        return snapshots

    def purge_expired_snapshots(self, max_age_hours: int = 24, max_total_size_mb: int = 500) -> int:
        """
        Purge snapshots older than max_age_hours or if total size exceeds max_total_size_mb cap.
        Returns the number of purged snapshot directories.
        """
        if not self.staging_dir.exists():
            return 0

        now = time.time()
        max_age_seconds = max_age_hours * 3600
        purged_count = 0

        snapshots = self.list_snapshots()
        total_size_bytes = 0

        for s in snapshots:
            folder = self.staging_dir / s["snapshot_id"]
            created_at = s.get("created_at", 0)
            age = now - created_at

            # Calculate folder size
            folder_size = sum(f.stat().st_size for f in folder.glob("**/*") if f.is_file())
            total_size_bytes += folder_size

            # Purge if too old or if size limit exceeded
            if age > max_age_seconds or (total_size_bytes > max_total_size_mb * 1024 * 1024):
                try:
                    shutil.rmtree(folder)
                    purged_count += 1
                except Exception as exc:
                    logger.warning("Failed to purge snapshot folder", folder=str(folder), error=str(exc))

        if purged_count > 0:
            logger.info("Purged expired undo snapshots", count=purged_count)
        return purged_count


_global_shadow_copy_service: ShadowCopyService | None = None


def get_shadow_copy_service() -> ShadowCopyService:
    global _global_shadow_copy_service
    if _global_shadow_copy_service is None:
        _global_shadow_copy_service = ShadowCopyService()
    return _global_shadow_copy_service
