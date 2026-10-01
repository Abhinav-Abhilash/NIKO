
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError, ValidationFailedError
from backend.app.db.models.note import NoteItem
from backend.app.db.session import get_session_maker


class NoteService:
    """Service layer managing local note items in SQLite."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        session_factory = get_session_maker()
        return session_factory()


    async def add_note(
        self, title: str, content: str, tags: str | None = None, user_id: str | None = None
    ) -> NoteItem:
        title = title.strip()
        if not title:
            raise ValidationFailedError("Note title cannot be empty.")
        content = content.strip()
        if not content:
            raise ValidationFailedError("Note content cannot be empty.")

        session = await self._get_session()
        note = NoteItem(
            title=title,
            content=content,
            tags=tags.strip() if tags else None,
            user_id=user_id,
        )
        session.add(note)
        await session.commit()
        await session.refresh(note)
        return note

    async def list_notes(self, user_id: str | None = None, limit: int = 50) -> list[NoteItem]:
        session = await self._get_session()
        stmt = select(NoteItem).order_by(NoteItem.created_at.desc()).limit(limit)
        if user_id:
            stmt = stmt.where(NoteItem.user_id == user_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search_notes(self, query: str, user_id: str | None = None) -> list[NoteItem]:
        query = query.strip()
        if not query:
            return await self.list_notes(user_id=user_id)

        session = await self._get_session()
        pattern = f"%{query}%"
        stmt = (
            select(NoteItem)
            .where(
                (NoteItem.title.ilike(pattern))
                | (NoteItem.content.ilike(pattern))
                | (NoteItem.tags.ilike(pattern))
            )
            .order_by(NoteItem.created_at.desc())
        )
        if user_id:
            stmt = stmt.where(NoteItem.user_id == user_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def delete_note(self, note_id: str, user_id: str | None = None) -> bool:
        session = await self._get_session()
        stmt = select(NoteItem).where(NoteItem.id == note_id)
        if user_id:
            stmt = stmt.where(NoteItem.user_id == user_id)
        res = await session.execute(stmt)
        note = res.scalar_one_or_none()
        if not note:
            raise NotFoundError(f"Note with ID '{note_id}' not found.")

        await session.delete(note)
        await session.commit()
        return True
