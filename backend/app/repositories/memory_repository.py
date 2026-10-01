import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.db.models.memory import Memory

logger = get_logger("niko.repositories.memory")


class MemoryRepositoryInterface(ABC):
    """Abstract interface for memory persistence and search (SQLite FTS5 / future Postgres pgvector/tsvector)."""

    @abstractmethod
    async def create_memory(
        self,
        user_id: str,
        content: str,
        keywords: str = "",
        key: str | None = None,
        category: str = "general",
        source: str = "user_stated",
        pinned: bool = False,
        enabled: bool = True,
    ) -> Memory:
        pass

    @abstractmethod
    async def get_memory(self, memory_id: str, user_id: str | None = None) -> Memory | None:
        pass

    @abstractmethod
    async def get_memory_by_key(self, key: str, user_id: str) -> Memory | None:
        pass

    @abstractmethod
    async def update_memory(
        self,
        memory_id: str,
        user_id: str | None = None,
        content: str | None = None,
        keywords: str | None = None,
        key: str | None = None,
        category: str | None = None,
        pinned: bool | None = None,
        enabled: bool | None = None,
        source: str | None = None,
    ) -> Memory | None:
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str, user_id: str | None = None) -> bool:
        pass

    @abstractmethod
    async def list_memories(
        self,
        user_id: str,
        category: str | None = None,
        pinned_only: bool = False,
        enabled_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Memory]:
        pass

    @abstractmethod
    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> list[Memory]:
        pass

    @abstractmethod
    async def get_pinned_profile(self, user_id: str, limit: int = 10) -> list[Memory]:
        pass

    @abstractmethod
    async def touch_memory(self, memory_id: str) -> None:
        pass

    @abstractmethod
    async def count_memories(self, user_id: str) -> int:
        pass


def sanitize_fts5_query(query: str) -> str:
    """
    Format and sanitize user query for SQLite FTS5 BM25 search:
    - Strips special FTS5 operators and punctuation.
    - Joins words with disjunctive 'OR' so missing words do not cause total search failure.
    - Adds prefix wildcard for sub-token/stem flexibility.
    """
    tokens = re.findall(r"\b[\w\-]+\b", query)
    if not tokens:
        return ""
    # Disjunctive OR query with token matching
    terms: list[str] = []
    for token in tokens:
        clean = token.replace('"', "").strip()
        if len(clean) >= 2:
            terms.append(f'"{clean}"*')
        elif clean:
            terms.append(f'"{clean}"')
    return " OR ".join(terms) if terms else ""


class SQLiteMemoryRepository(MemoryRepositoryInterface):
    """
    SQLite implementation of MemoryRepository using native FTS5 and BM25 ranking.
    Supports memory deduplication, memory count caps, and disjunctive query expansion.
    """

    def __init__(self, db: AsyncSession, max_memory_cap: int = 500) -> None:
        self.db = db
        self.max_memory_cap = max_memory_cap

    async def count_memories(self, user_id: str) -> int:
        stmt = select(func.count(Memory.id)).where(Memory.user_id == user_id)
        res = await self.db.execute(stmt)
        return int(res.scalar() or 0)

    async def _enforce_memory_cap(self, user_id: str) -> None:
        """Evicts oldest unpinned memories if user exceeds max_memory_cap."""
        current_count = await self.count_memories(user_id)
        if current_count < self.max_memory_cap:
            return

        excess = (current_count - self.max_memory_cap) + 1
        stmt = (
            select(Memory.id)
            .where(Memory.user_id == user_id, Memory.pinned.is_(False))
            .order_by(Memory.last_used_at.asc().nulls_first(), Memory.created_at.asc())
            .limit(excess)
        )
        res = await self.db.execute(stmt)
        ids_to_evict = list(res.scalars().all())

        if ids_to_evict:
            del_stmt = delete(Memory).where(Memory.id.in_(ids_to_evict))
            await self.db.execute(del_stmt)
            logger.info("Evicted oldest memories under cap limit", count=len(ids_to_evict), user_id=user_id)

    async def _find_duplicate(self, user_id: str, content: str, key: str | None = None) -> Memory | None:
        """Finds existing memory with identical key or identical normalized content."""
        if key:
            key_stmt = select(Memory).where(Memory.user_id == user_id, Memory.key == key.strip().lower())
            res_key = await self.db.execute(key_stmt)
            existing_key = res_key.scalar_one_or_none()
            if existing_key:
                return existing_key

        norm_content = " ".join(content.strip().lower().split())
        content_stmt = select(Memory).where(Memory.user_id == user_id)
        res = await self.db.execute(content_stmt)
        all_user_memories = res.scalars().all()
        for mem in all_user_memories:
            if " ".join(mem.content.strip().lower().split()) == norm_content:
                return mem
        return None

    async def create_memory(
        self,
        user_id: str,
        content: str,
        keywords: str = "",
        key: str | None = None,
        category: str = "general",
        source: str = "user_stated",
        pinned: bool = False,
        enabled: bool = True,
    ) -> Memory:
        clean_content = content.strip()
        clean_key = key.strip().lower() if key else None
        clean_category = category.strip().lower() if category else "general"

        # Deduplication check
        existing = await self._find_duplicate(user_id, clean_content, clean_key)
        if existing:
            # Update keywords and refresh timestamp rather than inserting duplicate
            combined_keywords = set(existing.keywords.split()) | set(keywords.split())
            existing.keywords = " ".join(sorted(combined_keywords))
            existing.updated_at = datetime.now(UTC)
            if pinned:
                existing.pinned = True
            await self.db.flush()
            logger.info("Deduplicated memory updated with new keywords", memory_id=existing.id)
            return existing

        # Memory cap enforcement
        await self._enforce_memory_cap(user_id)

        memory = Memory(
            user_id=user_id,
            content=clean_content,
            keywords=keywords.strip(),
            key=clean_key,
            category=clean_category,
            source=source,
            pinned=pinned,
            enabled=enabled,
        )
        self.db.add(memory)
        await self.db.flush()
        return memory

    async def get_memory(self, memory_id: str, user_id: str | None = None) -> Memory | None:
        stmt = select(Memory).where(Memory.id == memory_id)
        if user_id:
            stmt = stmt.where(Memory.user_id == user_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    get_memory_by_id = get_memory

    async def get_memory_by_key(self, key: str, user_id: str) -> Memory | None:
        stmt = select(Memory).where(Memory.key == key.strip().lower(), Memory.user_id == user_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def update_memory(
        self,
        memory_id: str,
        user_id: str | None = None,
        content: str | None = None,
        keywords: str | None = None,
        key: str | None = None,
        category: str | None = None,
        pinned: bool | None = None,
        enabled: bool | None = None,
        source: str | None = None,
    ) -> Memory | None:
        memory = await self.get_memory(memory_id, user_id=user_id)
        if not memory:
            return None

        if content is not None:
            memory.content = content.strip()
        if keywords is not None:
            memory.keywords = keywords.strip()
        if key is not None:
            memory.key = key.strip().lower() if key else None
        if category is not None:
            memory.category = category.strip().lower()
        if pinned is not None:
            memory.pinned = pinned
        if enabled is not None:
            memory.enabled = enabled
        if source is not None:
            memory.source = source

        memory.updated_at = datetime.now(UTC)
        await self.db.flush()
        return memory

    async def delete_memory(self, memory_id: str, user_id: str | None = None) -> bool:
        memory = await self.get_memory(memory_id, user_id=user_id)
        if not memory:
            return False
        await self.db.delete(memory)
        await self.db.flush()
        return True

    async def list_memories(
        self,
        user_id: str,
        category: str | None = None,
        pinned_only: bool = False,
        enabled_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Memory]:
        stmt = select(Memory).where(Memory.user_id == user_id)
        if category:
            stmt = stmt.where(Memory.category == category.strip().lower())
        if pinned_only:
            stmt = stmt.where(Memory.pinned.is_(True))
        if enabled_only:
            stmt = stmt.where(Memory.enabled.is_(True))

        stmt = stmt.order_by(Memory.pinned.desc(), Memory.created_at.desc()).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> list[Memory]:
        match_query = sanitize_fts5_query(query)
        if not match_query:
            # If query sanitization results in empty terms, fallback to recent memories
            return await self.list_memories(
                user_id=user_id,
                category=category,
                enabled_only=enabled_only,
                limit=limit,
            )

        sql = (
            "SELECT m.id, bm25(memories_fts) as rank "
            "FROM memories_fts fts "
            "JOIN memories m ON m.id = fts.memory_id "
            "WHERE memories_fts MATCH :match_query AND m.user_id = :user_id "
        )
        params: dict[str, Any] = {"match_query": match_query, "user_id": user_id, "limit": limit}

        if category:
            sql += "AND m.category = :category "
            params["category"] = category.strip().lower()

        if enabled_only:
            sql += "AND m.enabled = 1 "

        sql += "ORDER BY rank LIMIT :limit"

        raw_res = await self.db.execute(text(sql), params)
        matched_ids = [row[0] for row in raw_res.fetchall()]

        if not matched_ids:
            return []

        # Fetch ORM objects preserving ranking order
        mem_stmt = select(Memory).where(Memory.id.in_(matched_ids))
        res = await self.db.execute(mem_stmt)
        memories_map = {m.id: m for m in res.scalars().all()}

        ordered_memories = [memories_map[mid] for mid in matched_ids if mid in memories_map]
        return ordered_memories

    async def get_pinned_profile(self, user_id: str, limit: int = 10) -> list[Memory]:
        stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.enabled.is_(True),
                (Memory.pinned.is_(True) | (Memory.category == "profile")),
            )
            .order_by(Memory.created_at.asc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def touch_memory(self, memory_id: str) -> None:
        stmt = select(Memory).where(Memory.id == memory_id)
        res = await self.db.execute(stmt)
        mem = res.scalar_one_or_none()
        if mem:
            mem.last_used_at = datetime.now(UTC)
            await self.db.flush()
