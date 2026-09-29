from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import Session


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_session(
        self,
        user_id: str,
        refresh_token_hash: str,
        family_id: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Session:
        session = Session(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            family_id=family_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            is_revoked=False,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_by_refresh_token_hash(self, token_hash: str) -> Session | None:
        query = select(Session).options(selectinload(Session.user)).where(Session.refresh_token_hash == token_hash)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def revoke_session(self, session_id: str) -> None:
        await self.db.execute(
            update(Session).where(Session.id == session_id).values(is_revoked=True)
        )

    async def revoke_family(self, family_id: str) -> None:
        """Revoke all sessions sharing the same family ID (reuse detection defense)."""
        await self.db.execute(
            update(Session).where(Session.family_id == family_id).values(is_revoked=True)
        )
