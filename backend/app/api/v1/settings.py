from typing import Any
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_owner
from backend.app.llm.cooldown import cooldown_tracker
from backend.app.llm.discovery import model_discovery
from backend.app.llm.types import ModelRolesConfig
from backend.app.repositories.settings_repository import SettingsRepository

router = APIRouter(prefix="/settings", tags=["Settings & Model Roles"])


@router.get("/roles", response_model=ModelRolesConfig)
async def get_model_roles(
    current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> ModelRolesConfig:
    """Retrieve the current ordered model roles configuration."""
    repo = SettingsRepository(db)
    return await repo.get_model_roles_config()


@router.put("/roles", response_model=ModelRolesConfig)
async def update_model_roles(
    config: ModelRolesConfig,
    request: Request,
    current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> ModelRolesConfig:
    """
    Update the ordered model roles configuration.
    Stored in the settings table and used by the LLM orchestrator.
    """
    repo = SettingsRepository(db)
    await repo.save_model_roles_config(config)
    await db.commit()
    return config


@router.post("/models/refresh")
async def refresh_models(
    request: Request,
    current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
    app_settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """
    Admin refresh: queries live endpoints for Gemini, Groq, and OpenRouter
    to discover active available models and filter for free tool-capable models.
    """
    repo = SettingsRepository(db)
    keys = await repo.get_decrypted_provider_keys(app_settings.ENCRYPTION_KEY)
    # Also fallback to env vars if not stored in DB
    if "gemini" not in keys and app_settings.INITIAL_GEMINI_API_KEY:
        keys["gemini"] = app_settings.INITIAL_GEMINI_API_KEY
    if "groq" not in keys and app_settings.INITIAL_GROQ_API_KEY:
        keys["groq"] = app_settings.INITIAL_GROQ_API_KEY
    if "openrouter" not in keys and app_settings.INITIAL_OPENROUTER_API_KEY:
        keys["openrouter"] = app_settings.INITIAL_OPENROUTER_API_KEY

    discovered = await model_discovery.refresh_all(keys)
    return {
        "status": "refreshed",
        "discovered_models": discovered,
    }


@router.get("/models/status")
async def get_models_status(
    current_owner: User = Depends(get_current_owner),
) -> dict[str, Any]:
    """Return predictive cooldown and rate-limit consumption status."""
    return {
        "discovered": model_discovery.get_discovered_summary(),
        "quotas": cooldown_tracker.get_status(),
    }
