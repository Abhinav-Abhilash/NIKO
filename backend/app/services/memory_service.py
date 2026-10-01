import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.logging import get_logger
from backend.app.db.models import Setting, User
from backend.app.db.models.memory import Memory
from backend.app.llm.orchestrator import get_llm_orchestrator
from backend.app.llm.types import LLMMessage, ModelRole
from backend.app.repositories.memory_repository import (
    MemoryRepositoryInterface,
    SQLiteMemoryRepository,
)
from backend.app.services.memory_safety import (
    contains_injection_phrases,
    contains_secrets,
)

logger = get_logger("niko.memory_service")

# Rule-based fallback synonyms for when LLM is offline or fast heuristic matching is preferred
FALLBACK_SYNONYMS: dict[str, list[str]] = {
    "sister": ["sibling", "family", "sis"],
    "brother": ["sibling", "family", "bro"],
    "mother": ["mom", "parent", "family"],
    "father": ["dad", "parent", "family"],
    "birthday": ["bday", "birthdate", "anniversary", "born"],
    "car": ["vehicle", "automobile", "auto"],
    "work": ["job", "office", "employment", "career"],
    "home": ["house", "residence", "apartment"],
    "like": ["prefer", "love", "favorite", "enjoy"],
    "dislike": ["hate", "avoid", "allergic"],
}


class MemoryService:
    """
    Coordinates long-term memory operations:
    - Keywords & synonym enrichment via light utility model on save.
    - Query expansion fallback on weak recall.
    - Server-side provenance protection (untrusted external inputs require approval).
    - Secret scanner refusal and prompt injection defense.
    - Mode governance (manual, suggest, auto) and export capabilities.
    """

    def __init__(
        self,
        db: AsyncSession,
        repo: MemoryRepositoryInterface | None = None,
        orchestrator: Any | None = None,
    ) -> None:
        self.db = db
        self.repo = repo or SQLiteMemoryRepository(db)
        self.orchestrator = orchestrator

    def _get_orchestrator(self) -> Any:
        if self.orchestrator is None:
            self.orchestrator = get_llm_orchestrator()
        return self.orchestrator

    # -------------------------------------------------------------
    # Settings & Modes Governance
    # -------------------------------------------------------------

    async def is_memory_enabled(self) -> bool:
        """Check if long-term memory system is globally enabled."""
        stmt = select(Setting).where(Setting.key == "memory.enabled")
        res = await self.db.execute(stmt)
        setting = res.scalar_one_or_none()
        if not setting:
            return True
        try:
            return bool(json.loads(setting.value_json))
        except Exception:
            return True

    async def get_memory_mode(self) -> str:
        """Get current memory mode: 'manual' | 'suggest' | 'auto' (default: 'auto')."""
        stmt = select(Setting).where(Setting.key == "memory.mode")
        res = await self.db.execute(stmt)
        setting = res.scalar_one_or_none()
        if not setting:
            return "auto"
        try:
            val = json.loads(setting.value_json)
            if val in ("manual", "suggest", "auto"):
                return str(val)
        except Exception:
            pass
        return "auto"

    async def set_memory_mode(self, mode: str, enabled: bool | None = None) -> None:
        """Configure memory mode and active status."""
        mode_clean = mode.strip().lower()
        if mode_clean not in ("manual", "suggest", "auto"):
            raise ValidationFailedError(
                f"Invalid memory mode '{mode}'. Must be 'manual', 'suggest', or 'auto'."
            )

        # Update mode
        stmt_mode = select(Setting).where(Setting.key == "memory.mode")
        res_mode = await self.db.execute(stmt_mode)
        setting_mode = res_mode.scalar_one_or_none()
        if not setting_mode:
            setting_mode = Setting(key="memory.mode", value_json=json.dumps(mode_clean), category="memory")
            self.db.add(setting_mode)
        else:
            setting_mode.value_json = json.dumps(mode_clean)

        # Update enabled
        if enabled is not None:
            stmt_en = select(Setting).where(Setting.key == "memory.enabled")
            res_en = await self.db.execute(stmt_en)
            setting_en = res_en.scalar_one_or_none()
            if not setting_en:
                setting_en = Setting(key="memory.enabled", value_json=json.dumps(enabled), category="memory")
                self.db.add(setting_en)
            else:
                setting_en.value_json = json.dumps(enabled)

        await self.db.flush()
        logger.info("Updated memory configuration", mode=mode_clean, enabled=enabled)

    # -------------------------------------------------------------
    # Light-Model Keyword Enrichment & Query Expansion
    # -------------------------------------------------------------

    async def generate_keywords(
        self, content: str, key: str | None = None, category: str | None = None
    ) -> str:
        """
        Enrich memory with related terms, synonyms, aliases, and colloquial abbreviations
        using the light utility model (or rule-based fallback).
        """
        extracted_keywords: set[str] = set()

        # 1. Apply rule-based synonyms for immediate baseline coverage
        words = re.findall(r"\b[a-zA-Z]{3,}\b", content.lower())
        for w in words:
            if w in FALLBACK_SYNONYMS:
                extracted_keywords.update(FALLBACK_SYNONYMS[w])

        # 2. Query light utility model if available
        try:
            orch = self._get_orchestrator()
            prompt = (
                f"Analyze this fact to extract 4-8 search synonyms, related concepts, and informal abbreviations.\n"
                f"Fact: {content}\n"
                f"Key: {key or 'none'}\n"
                f"Category: {category or 'general'}\n"
                f"Return ONLY comma-separated lowercase words (no explanation, no bullet points)."
            )
            resp = await orch.chat(
                role=ModelRole.LIGHT,
                messages=[LLMMessage(role="user", content=prompt)],
            )
            raw_terms = resp.content.strip()
            for term in raw_terms.split(","):
                clean = re.sub(r"[^\w\-]", "", term.strip().lower())
                if len(clean) >= 2:
                    extracted_keywords.add(clean)
        except Exception as exc:
            logger.debug("Light model keyword enrichment skipped; using rule-based synonyms", error=str(exc))

        if key:
            extracted_keywords.add(key.lower())
        if category:
            extracted_keywords.add(category.lower())

        return " ".join(sorted(extracted_keywords))

    async def expand_search_query(self, query: str) -> str:
        """
        Expands weak or few-match queries with alternative synonyms or related concepts
        using the light utility model (or rule-based fallback).
        """
        expanded: set[str] = set()
        words = re.findall(r"\b[a-zA-Z]{3,}\b", query.lower())
        for w in words:
            if w in FALLBACK_SYNONYMS:
                expanded.update(FALLBACK_SYNONYMS[w])

        try:
            orch = self._get_orchestrator()
            prompt = (
                f"Given the user search query: '{query}'\n"
                f"Provide 3-6 alternate keywords, synonyms, or short abbreviations that mean the same thing.\n"
                f"Return ONLY comma-separated lowercase words."
            )
            resp = await orch.chat(
                role=ModelRole.LIGHT,
                messages=[LLMMessage(role="user", content=prompt)],
            )
            for term in resp.content.strip().split(","):
                clean = re.sub(r"[^\w\-]", "", term.strip().lower())
                if len(clean) >= 2:
                    expanded.add(clean)
        except Exception as exc:
            logger.debug("Query expansion fallback skipped", error=str(exc))

        return " ".join(sorted(expanded))

    # -------------------------------------------------------------
    # Memory Core Operations
    # -------------------------------------------------------------

    async def remember(
        self,
        user_id: str,
        content: str,
        key: str | None = None,
        category: str = "general",
        source: str = "user_stated",
        pinned: bool = False,
        provenance: str = "direct",
    ) -> dict[str, Any]:
        """
        Save or suggest a memory with strict safety validation:
        - Refuses secrets, private keys, passwords, API tokens.
        - Checks for prompt injection phrases.
        - Provenance rule: untrusted external source (web/file/OCR) NEVER writes silently;
          it creates a suggestion or requires approval.
        """
        clean_content = content.strip()
        if not clean_content:
            raise ValidationFailedError("Memory content cannot be empty.")

        # 1. Safety check: Secret Scanner Refusal
        has_secret, secret_reason = contains_secrets(clean_content)
        if has_secret:
            raise ValidationFailedError(secret_reason or "Credentials cannot be stored in long-term memory.")

        # 2. Safety check: Minor prompt injection phrase detection
        has_injection, injection_reason = contains_injection_phrases(clean_content)
        if has_injection:
            raise ValidationFailedError(injection_reason or "Memory content contains forbidden injection patterns.")

        # 3. Check if memory is enabled
        if not await self.is_memory_enabled():
            return {
                "success": False,
                "saved": False,
                "reason": "Long-term memory is currently disabled in settings.",
            }

        # 4. Server-Side Provenance Enforcement
        # Untrusted external data (web/file/ocr) NEVER writes silently to memory
        if provenance == "external_untrusted":
            logger.info("Remember call from untrusted provenance converted to suggestion", user_id=user_id)
            return {
                "success": False,
                "saved": False,
                "requires_approval": True,
                "reason": "Memory proposed from untrusted external source requires explicit owner approval.",
                "suggested_memory": {
                    "content": clean_content,
                    "key": key,
                    "category": category,
                    "source": "untrusted",
                },
            }

        # 5. Check memory mode ('manual' | 'suggest' | 'auto')
        mode = await self.get_memory_mode()
        if mode == "suggest" and source not in ("approved", "owner_confirmed"):
            return {
                "success": False,
                "saved": False,
                "requires_approval": True,
                "reason": "Memory mode is set to 'suggest'; requires confirmation before saving.",
                "suggested_memory": {
                    "content": clean_content,
                    "key": key,
                    "category": category,
                    "source": "suggested",
                },
            }

        # 6. Generate keywords via light model / rule-based enrichment
        keywords = await self.generate_keywords(clean_content, key=key, category=category)

        # Ensure user exists in users table to satisfy foreign key constraint
        if user_id:
            user_exists = (
                await self.db.execute(select(User.id).where(User.id == user_id))
            ).scalar_one_or_none()
            if not user_exists:
                default_user = User(
                    id=user_id,
                    username=f"user_{user_id[:8]}",
                    password_hash="system_managed",
                    role="owner",
                )
                self.db.add(default_user)
                await self.db.flush()
        else:
            first_user = (await self.db.execute(select(User).limit(1))).scalar_one_or_none()
            if first_user:
                user_id = first_user.id
            else:
                default_user = User(
                    username="operator",
                    password_hash="system_managed",
                    role="owner",
                )
                self.db.add(default_user)
                await self.db.flush()
                user_id = default_user.id

        # 7. Persist to repository with deduplication and cap enforcement
        memory = await self.repo.create_memory(
            user_id=user_id,
            content=clean_content,
            keywords=keywords,
            key=key,
            category=category,
            source=source,
            pinned=pinned,
            enabled=True,
        )

        return {
            "success": True,
            "saved": True,
            "memory_id": memory.id,
            "key": memory.key,
            "category": memory.category,
            "keywords": memory.keywords,
            "pinned": memory.pinned,
        }

    async def recall(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        category: str | None = None,
    ) -> list[Memory]:
        """
        Search memories using FTS5 BM25 with query expansion fallback on weak recall.
        """
        if not await self.is_memory_enabled():
            return []

        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Primary search with user query
        results = await self.repo.search_memories(
            user_id=user_id,
            query=clean_query,
            limit=limit,
            category=category,
        )

        # 2. Expansion fallback: If 0 or weak results, expand query with related synonyms
        if len(results) < 1:
            expansion = await self.expand_search_query(clean_query)
            if expansion:
                combined_query = f"{clean_query} {expansion}"
                logger.info("Executing expanded memory search fallback", query=clean_query, expansion=expansion)
                results = await self.repo.search_memories(
                    user_id=user_id,
                    query=combined_query,
                    limit=limit,
                    category=category,
                )

        # Touch retrieved memories to refresh last_used_at
        for mem in results:
            await self.repo.touch_memory(mem.id)

        return results

    async def get_memory(self, memory_id: str, user_id: str | None = None) -> Memory | None:
        """Fetch a single memory by ID."""
        return await self.repo.get_memory(memory_id, user_id=user_id)

    async def update_memory(
        self,
        memory_id: str,
        user_id: str | None = None,
        content: str | None = None,
        key: str | None = None,
        category: str | None = None,
        pinned: bool | None = None,
        enabled: bool | None = None,
    ) -> Memory | None:
        """Update an existing memory with validation and keyword regeneration if content changed."""
        keywords: str | None = None
        if content is not None:
            clean_content = content.strip()
            if not clean_content:
                raise ValidationFailedError("Memory content cannot be empty.")
            has_secret, secret_reason = contains_secrets(clean_content)
            if has_secret:
                raise ValidationFailedError(secret_reason or "Credentials cannot be stored in memory.")
            has_injection, injection_reason = contains_injection_phrases(clean_content)
            if has_injection:
                raise ValidationFailedError(injection_reason or "Content contains forbidden injection patterns.")
            keywords = await self.generate_keywords(clean_content, key=key, category=category)
            content = clean_content

        return await self.repo.update_memory(
            memory_id=memory_id,
            user_id=user_id,
            content=content,
            keywords=keywords,
            key=key,
            category=category,
            pinned=pinned,
            enabled=enabled,
        )

    async def forget(
        self,
        user_id: str,
        memory_id: str | None = None,
        key: str | None = None,
    ) -> bool:
        """Delete memory by ID or unique key."""
        target_id = memory_id
        if not target_id and key:
            mem = await self.repo.get_memory_by_key(key, user_id=user_id)
            if mem:
                target_id = mem.id

        if not target_id:
            return False

        return await self.repo.delete_memory(target_id, user_id=user_id)

    async def list_memories(
        self,
        user_id: str,
        category: str | None = None,
        pinned_only: bool = False,
        enabled_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Memory]:
        return await self.repo.list_memories(
            user_id=user_id,
            category=category,
            pinned_only=pinned_only,
            enabled_only=enabled_only,
            limit=limit,
            offset=offset,
        )

    async def get_pinned_profile(self, user_id: str, limit: int = 10) -> list[Memory]:
        """Fetch core user profile facts and pinned memories."""
        return await self.repo.get_pinned_profile(user_id=user_id, limit=limit)

    async def export_memories(self, user_id: str) -> list[dict[str, Any]]:
        """Export all memories for backup or export."""
        memories = await self.list_memories(user_id=user_id, enabled_only=False, limit=1000)
        return [
            {
                "id": m.id,
                "key": m.key,
                "content": m.content,
                "keywords": m.keywords,
                "category": m.category,
                "source": m.source,
                "pinned": m.pinned,
                "enabled": m.enabled,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
                "last_used_at": m.last_used_at.isoformat() if m.last_used_at else None,
            }
            for m in memories
        ]
