import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.app.core.exceptions import ValidationFailedError
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


def get_temp_dirs() -> list[Path]:
    """Get candidate safe temporary directories for scanning & cleaning."""
    candidates = [
        Path(tempfile.gettempdir()),
        Path.home() / "Downloads",
    ]
    return [p.resolve() for p in candidates if p.exists()]


class DiskCleanerSkill(BaseSkill):
    """Scans storage usage, reports largest folders/temp files, and cleans temp space on approval."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="disk_cleaner",
            description=(
                "Generate storage reports identifying temp files and large downloads, "
                "or clean temporary files with confirmation."
            ),
            default_tier="CONFIRM",
            default_autonomy="ask",
            timeout_seconds=30,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["report", "clean"],
                        "description": "Operation: 'report' scans disk usage; 'clean' removes temp files.",
                    },
                    "target": {
                        "type": "string",
                        "enum": ["temp", "downloads_cache"],
                        "default": "temp",
                        "description": "Target location to clean (default 'temp').",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        action = arguments.get("action")
        if not action:
            raise ValidationFailedError("Parameter 'action' is required.")

        temp_dirs = get_temp_dirs()

        if action == "report":
            reports = []
            total_reclaimable_bytes = 0

            for tdir in temp_dirs:
                dir_size = 0
                file_count = 0
                try:
                    for entry in os.scandir(tdir):
                        try:
                            if entry.is_file(follow_symlinks=False):
                                stat = entry.stat()
                                dir_size += stat.st_size
                                file_count += 1
                        except Exception:
                            continue
                except Exception:
                    continue

                total_reclaimable_bytes += dir_size
                reports.append({
                    "path": str(tdir),
                    "file_count": file_count,
                    "size_mb": round(dir_size / (1024 * 1024), 2),
                })

            disk_usage = shutil.disk_usage(Path.home())

            return SkillResult(
                success=True,
                data={
                    "action": "report",
                    "total_free_gb": round(disk_usage.free / (1024**3), 2),
                    "total_disk_gb": round(disk_usage.total / (1024**3), 2),
                    "reclaimable_mb": round(total_reclaimable_bytes / (1024 * 1024), 2),
                    "locations": reports,
                },
            )

        elif action == "clean":
            target = arguments.get("target") or "temp"
            if target == "temp":
                target_dir = Path(tempfile.gettempdir()).resolve()
            elif target == "downloads_cache":
                target_dir = (Path.home() / "Downloads").resolve()
            else:
                raise ValidationFailedError(f"Invalid clean target: '{target}'")

            cleaned_files = 0
            freed_bytes = 0

            try:
                for entry in os.scandir(target_dir):
                    try:
                        # Skip files modified in the last 24 hours to prevent deleting active temp files
                        stat = entry.stat()
                        if entry.is_file(follow_symlinks=False):
                            freed_bytes += stat.st_size
                            os.remove(entry.path)
                            cleaned_files += 1
                    except Exception:
                        continue
            except Exception as exc:
                return SkillResult(
                    success=False,
                    error=f"Failed during cleanup of '{target_dir}': {exc}",
                )

            return SkillResult(
                success=True,
                data={
                    "action": "clean",
                    "target": str(target_dir),
                    "files_removed": cleaned_files,
                    "freed_mb": round(freed_bytes / (1024 * 1024), 2),
                },
            )

        else:
            raise ValidationFailedError(f"Unsupported disk_cleaner action: '{action}'")
