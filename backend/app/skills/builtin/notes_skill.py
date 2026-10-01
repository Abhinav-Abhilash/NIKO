from typing import Any

from backend.app.core.exceptions import ValidationFailedError
from backend.app.services.note_service import NoteService
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class NotesSkill(BaseSkill):
    """Manages local notes and task lists in SQLite."""

    def __init__(self, note_service: NoteService | None = None) -> None:
        self.note_service = note_service or NoteService()

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="notes",
            description=(
                "Create, search, list, or delete local notes and task lists stored in SQLite."
            ),
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=10,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "list", "search", "delete"],
                        "description": "Operation to perform on notes.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Short title or summary of the note (required for add).",
                    },
                    "content": {
                        "type": "string",
                        "description": "Detailed text content of the note (required for add).",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Optional comma-separated tags for categorization (e.g. 'work,todo').",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search keyword query (used for search action).",
                    },
                    "note_id": {
                        "type": "string",
                        "description": "ID of the note to delete (required for delete).",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], context: SkillContext) -> SkillResult:
        action = arguments.get("action")
        if not action:
            raise ValidationFailedError("Parameter 'action' is required.")

        if action == "add":
            title = arguments.get("title") or ""
            content = arguments.get("content") or ""
            tags = arguments.get("tags")

            note = await self.note_service.add_note(
                title=title,
                content=content,
                tags=tags,
                user_id=context.user_id,
            )
            return SkillResult(
                success=True,
                data={
                    "action": "add",
                    "id": note.id,
                    "title": note.title,
                    "content": note.content,
                    "tags": note.tags,
                    "created_at": note.created_at.isoformat(),
                },
            )

        elif action == "list":
            notes = await self.note_service.list_notes(user_id=context.user_id)
            return SkillResult(
                success=True,
                data={
                    "action": "list",
                    "count": len(notes),
                    "notes": [
                        {
                            "id": n.id,
                            "title": n.title,
                            "content": n.content,
                            "tags": n.tags,
                            "created_at": n.created_at.isoformat(),
                        }
                        for n in notes
                    ],
                },
            )

        elif action == "search":
            query = arguments.get("query") or ""
            notes = await self.note_service.search_notes(query=query, user_id=context.user_id)
            return SkillResult(
                success=True,
                data={
                    "action": "search",
                    "query": query,
                    "count": len(notes),
                    "notes": [
                        {
                            "id": n.id,
                            "title": n.title,
                            "content": n.content,
                            "tags": n.tags,
                            "created_at": n.created_at.isoformat(),
                        }
                        for n in notes
                    ],
                },
            )

        elif action == "delete":
            note_id = arguments.get("note_id")
            if not note_id:
                raise ValidationFailedError("Parameter 'note_id' is required for delete action.")

            await self.note_service.delete_note(note_id=note_id, user_id=context.user_id)
            return SkillResult(
                success=True,
                data={"action": "delete", "id": note_id, "deleted": True},
            )

        else:
            raise ValidationFailedError(f"Unsupported notes action: '{action}'")
