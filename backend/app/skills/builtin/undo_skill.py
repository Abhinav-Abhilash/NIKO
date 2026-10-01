from typing import Any

from backend.app.core.exceptions import ValidationFailedError
from backend.app.services.shadow_copy_service import get_shadow_copy_service
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class UndoSkill(BaseSkill):
    """Reverts previous file mutations or automation actions using local shadow copies."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="undo",
            description=(
                "Revert the last file modification, deletion, or automation action "
                "using shadow copies staged in storage/undo_staging."
            ),
            default_tier="CONFIRM",
            default_autonomy="ask",
            timeout_seconds=15,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["undo_last", "list_snapshots", "revert_id"],
                        "description": "Undo operation to perform.",
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": "Specific snapshot ID to restore (for revert_id action).",
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

        service = get_shadow_copy_service()

        if action == "list_snapshots":
            snapshots = service.list_snapshots()
            return SkillResult(
                success=True,
                data={"snapshots": snapshots, "total": len(snapshots)},
            )

        elif action == "undo_last":
            res = service.restore_snapshot(snapshot_id=None)
            return SkillResult(
                success=res.get("success", False),
                data=res,
            )

        elif action == "revert_id":
            snap_id = arguments.get("snapshot_id")
            if not snap_id:
                raise ValidationFailedError("Parameter 'snapshot_id' is required for revert_id action.")
            res = service.restore_snapshot(snapshot_id=snap_id)
            return SkillResult(
                success=res.get("success", False),
                data=res,
            )

        else:
            raise ValidationFailedError(f"Unsupported undo action: '{action}'")
