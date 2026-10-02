from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
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
    _current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> ModelRolesConfig:
    """Retrieve the current ordered model roles configuration."""
    repo = SettingsRepository(db)
    return await repo.get_model_roles_config()


@router.put("/roles", response_model=ModelRolesConfig)
async def update_model_roles(
    config: ModelRolesConfig,
    _request: Request,
    _current_owner: User = Depends(get_current_owner),
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
    _request: Request,
    _current_owner: User = Depends(get_current_owner),
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
    _current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return predictive cooldown, rate-limit consumption status, and active role-to-model map."""
    repo = SettingsRepository(db)
    roles = await repo.get_model_roles_config()
    return {
        "discovered": model_discovery.get_discovered_summary(),
        "quotas": cooldown_tracker.get_status(),
        "roles": roles.model_dump() if roles else {},
    }

class HotkeyConfig(BaseModel):
    hotkey: str = Field(default="Ctrl+Space", min_length=2, max_length=50)

    @field_validator("hotkey")
    @classmethod
    def validate_hotkey(cls, v: str) -> str:
        clean = v.strip()
        parts = [p.strip() for p in clean.replace("-", "+").split("+") if p.strip()]
        if not parts:
            raise ValueError("Hotkey cannot be empty")
        valid_modifiers = {"ctrl", "control", "alt", "shift", "super", "cmd", "command", "commandorcontrol"}
        has_mod = any(p.lower() in valid_modifiers for p in parts[:-1]) or len(parts) >= 2
        if not has_mod and len(parts) < 2:
            raise ValueError("Hotkey must include a modifier key (e.g. Ctrl, Alt, Shift) or key combination")
        return clean


@router.get("/hotkey", response_model=HotkeyConfig)
async def get_shell_hotkey(
    _current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> HotkeyConfig:
    """Retrieve the configured desktop overlay global hotkey."""
    repo = SettingsRepository(db)
    hotkey = await repo.get_hotkey()
    return HotkeyConfig(hotkey=hotkey)


@router.put("/hotkey", response_model=HotkeyConfig)
async def update_shell_hotkey(
    payload: HotkeyConfig,
    _request: Request,
    _current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> HotkeyConfig:
    """Update the desktop overlay global hotkey and sync to storage/shell_config.json."""
    repo = SettingsRepository(db)
    await repo.save_hotkey(payload.hotkey)
    await db.commit()
    return payload


class PersonaConfig(BaseModel):
    name: str = Field(default="NIKO", min_length=1, max_length=50)
    persona: str = Field(
        default="A friendly, embodied, and highly capable desktop AI companion.",
        max_length=2000,
    )


@router.get("/persona", response_model=PersonaConfig)
async def get_persona(
    _current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PersonaConfig:
    """Retrieve the pet's name and persona configuration."""
    repo = SettingsRepository(db)
    data = await repo.get_persona_config()
    return PersonaConfig(name=data["name"], persona=data["persona"])


@router.put("/persona", response_model=PersonaConfig)
async def update_persona(
    payload: PersonaConfig,
    _request: Request,
    _current_owner: User = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PersonaConfig:
    """Update the pet's name and persona configuration."""
    repo = SettingsRepository(db)
    await repo.save_persona_config(name=payload.name, persona=payload.persona)
    await db.commit()
    return payload


