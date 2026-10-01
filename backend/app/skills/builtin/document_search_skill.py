from typing import Any

from sqlalchemy import select

from backend.app.core.exceptions import ValidationFailedError
from backend.app.db.models import User
from backend.app.db.session import get_session_maker
from backend.app.services.document_service import DocumentService
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class DocumentSearchSkill(BaseSkill):
    """Searches indexed local documents and ingests files for local document Q&A."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="document_search",
            description=(
                "Search indexed local documents (PDFs, notes, markdown, code) "
                "or ingest new local files into the local knowledge base."
            ),
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=20,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["search", "ingest", "list"],
                        "description": "Operation: 'search' to query index, 'ingest' to index a file, 'list' to view indexed files.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query or keywords (required for 'search' action).",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Absolute file path to ingest (required for 'ingest' action).",
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 5,
                        "description": "Maximum number of matching chunks to return.",
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

        session_maker = get_session_maker()
        async with session_maker() as db:
            user_id = context.user_id
            if not user_id or user_id == "anonymous":
                res_owner = await db.execute(select(User).where(User.role == "owner").limit(1))
                owner_obj = res_owner.scalar_one_or_none()
                user_id = owner_obj.id if owner_obj else "owner"

            doc_service = DocumentService(db)

            if action == "search":
                query = (arguments.get("query") or "").strip()
                if not query:
                    raise ValidationFailedError("Parameter 'query' is required for search action.")
                top_k = min(int(arguments.get("top_k") or 5), 10)
                chunks = await doc_service.search(user_id=user_id, query=query, top_k=top_k)
                return SkillResult(
                    success=True,
                    data={"query": query, "results_count": len(chunks), "chunks": chunks},
                )

            elif action == "ingest":
                raw_path = arguments.get("file_path")
                if not raw_path:
                    raise ValidationFailedError("Parameter 'file_path' is required for ingest action.")
                doc = await doc_service.ingest_file(user_id=user_id, file_path_str=raw_path)
                return SkillResult(
                    success=True,
                    data={
                        "document_id": doc.id,
                        "title": doc.title,
                        "chunks_indexed": doc.chunk_count,
                        "status": "ingested",
                    },
                )

            elif action == "list":
                docs = await doc_service.list_documents(user_id=user_id)
                return SkillResult(
                    success=True,
                    data={
                        "documents": [
                            {
                                "id": d.id,
                                "title": d.title,
                                "file_path": d.file_path,
                                "chunk_count": d.chunk_count,
                                "file_type": d.file_type,
                            }
                            for d in docs
                        ],
                        "total": len(docs),
                    },
                )

            else:
                raise ValidationFailedError(f"Unsupported document_search action: '{action}'")
