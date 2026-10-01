import os
from pathlib import Path
from typing import Any

from backend.app.core.exceptions import ValidationFailedError
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


def get_approved_roots() -> list[Path]:
    """Return list of allowed directory roots for file search operations."""
    home = Path.home()
    roots = [
        home / "Documents",
        home / "Downloads",
        home / "Desktop",
        Path.cwd(),
    ]
    # Filter only existing directories
    return [r.resolve() for r in roots if r.exists()]


def is_path_approved(target_path: Path, approved_roots: list[Path]) -> bool:
    """Check if target path resides within at least one approved root directory."""
    resolved = target_path.resolve()
    for root in approved_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


class FileFinderSkill(BaseSkill):
    """Searches files by name or content within approved user folders and opens files safely."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="file_finder",
            description=(
                "Search files by name pattern or text content within approved directories "
                "(Documents, Downloads, Desktop, workspace). Safely open or reveal files."
            ),
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=20,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["search_name", "search_content", "open"],
                        "description": "Operation to perform.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Filename pattern (e.g. '*.py') or text snippet to search.",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to open or reveal (required for 'open' action).",
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 20,
                        "maximum": 50,
                        "description": "Maximum number of search results to return.",
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

        approved_roots = get_approved_roots()

        if action == "search_name":
            query = (arguments.get("query") or "").strip()
            if not query:
                raise ValidationFailedError("Parameter 'query' is required for search_name action.")

            max_results = min(int(arguments.get("max_results") or 20), 50)
            matches = []

            for root in approved_roots:
                try:
                    for p in root.rglob(f"*{query}*"):
                        if p.is_file():
                            matches.append({
                                "path": str(p),
                                "filename": p.name,
                                "size_bytes": p.stat().st_size,
                            })
                            if len(matches) >= max_results:
                                break
                except Exception:
                    continue
                if len(matches) >= max_results:
                    break

            return SkillResult(
                success=True,
                data={
                    "action": "search_name",
                    "query": query,
                    "results_count": len(matches),
                    "files": matches,
                },
            )

        elif action == "search_content":
            query = (arguments.get("query") or "").strip()
            if not query:
                raise ValidationFailedError("Parameter 'query' is required for search_content action.")

            max_results = min(int(arguments.get("max_results") or 20), 50)
            matches = []

            for root in approved_roots:
                try:
                    for p in root.rglob("*"):
                        if p.is_file() and p.stat().st_size < 5 * 1024 * 1024:  # 5MB limit
                            try:
                                text = p.read_text(encoding="utf-8", errors="ignore")
                                if query.lower() in text.lower():
                                    matches.append({
                                        "path": str(p),
                                        "filename": p.name,
                                        "size_bytes": p.stat().st_size,
                                    })
                                    if len(matches) >= max_results:
                                        break
                            except Exception:
                                continue
                except Exception:
                    continue
                if len(matches) >= max_results:
                    break

            return SkillResult(
                success=True,
                data={
                    "action": "search_content",
                    "query": query,
                    "results_count": len(matches),
                    "files": matches,
                },
            )

        elif action == "open":
            raw_path = arguments.get("file_path")
            if not raw_path:
                raise ValidationFailedError("Parameter 'file_path' is required for open action.")

            target_path = Path(raw_path).resolve()
            if not target_path.exists():
                return SkillResult(
                    success=False,
                    error=f"File path does not exist: '{raw_path}'",
                )

            if not is_path_approved(target_path, approved_roots):
                return SkillResult(
                    success=False,
                    error=f"Access denied: '{raw_path}' is outside approved user directories.",
                )

            os.startfile(str(target_path))  # Windows native file open
            return SkillResult(
                success=True,
                data={"action": "open", "file_path": str(target_path), "status": "opened"},
            )


        else:
            raise ValidationFailedError(f"Unsupported file_finder action: '{action}'")
