from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import InvalidSetupTokenError, SetupForbiddenError
from backend.app.core.security import encrypt_secret, hash_password
from backend.app.db.models import LLMProviderModel, User
from backend.app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication & Setup"])


class SetupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Owner username")
    password: str = Field(..., min_length=8, description="Owner password")
    setup_token: str | None = Field(
        None, description="One-time setup token (can also be passed via X-Setup-Token header)"
    )


class SetupResponse(BaseModel):
    message: str
    user_id: str
    username: str
    role: str
    providers_initialized: list[str]


@router.post("/setup", response_model=SetupResponse)
async def setup_initial_owner(
    req: SetupRequest,
    x_setup_token: str | None = Header(None, alias="X-Setup-Token"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SetupResponse:
    """
    One-time initial boot setup barrier.
    Requires the secret SETUP_TOKEN from server logs / .env.
    Once any owner exists, this endpoint is permanently disabled.
    """
    # 1. Check if an owner already exists
    count_query = select(func.count(User.id))
    result = await db.execute(count_query)
    user_count = result.scalar_one_or_none() or 0

    if user_count > 0:
        raise SetupForbiddenError(
            message="Owner account already initialized. The setup endpoint is permanently disabled."
        )

    # 2. Verify the one-time setup token
    provided_token = req.setup_token or x_setup_token
    if not provided_token or provided_token.strip() != settings.SETUP_TOKEN.strip():
        raise InvalidSetupTokenError(
            message="Invalid or missing setup token. Provide the one-time token from your terminal/env."
        )

    # 3. Create the initial owner
    hashed_pw = hash_password(req.password)
    owner = User(
        username=req.username.strip(),
        password_hash=hashed_pw,
        role="owner",
    )
    db.add(owner)

    # 4. Initialize default LLM providers with encrypted keys if present
    initialized_providers: list[str] = []

    provider_seeds: list[dict[str, Any]] = [
        {
            "name": "gemini",
            "default_model": "gemini-1.5-flash",
            "priority": 1,
            "key": settings.INITIAL_GEMINI_API_KEY,
        },
        {
            "name": "groq",
            "default_model": "llama-3.1-8b-instant",
            "priority": 2,
            "key": settings.INITIAL_GROQ_API_KEY,
        },
        {
            "name": "openrouter",
            "default_model": "meta-llama/llama-3.1-8b-instruct:free",
            "priority": 3,
            "key": settings.INITIAL_OPENROUTER_API_KEY,
        },
        {
            "name": "ollama",
            "default_model": "llama3.2:1b",
            "priority": 4,
            "key": None,
        },
    ]

    for seed in provider_seeds:
        encrypted_key = (
            encrypt_secret(seed["key"], settings.ENCRYPTION_KEY) if seed["key"] else None
        )
        provider = LLMProviderModel(
            name=seed["name"],
            default_model=seed["default_model"],
            priority=seed["priority"],
            encrypted_api_key=encrypted_key,
            enabled=True,
        )
        db.add(provider)
        initialized_providers.append(seed["name"])

    await db.commit()
    await db.refresh(owner)

    return SetupResponse(
        message="Owner account successfully created. Initial LLM providers registered.",
        user_id=owner.id,
        username=owner.username,
        role=owner.role,
        providers_initialized=initialized_providers,
    )
