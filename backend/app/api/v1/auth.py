import secrets
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import InvalidSetupTokenError, SetupForbiddenError
from backend.app.core.security import encrypt_secret, hash_password
from backend.app.db.models import LLMProviderModel, User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_user
from backend.app.services.auth_service import AuthService

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


class LoginRequest(BaseModel):
    username: str = Field(..., description="User username")
    password: str = Field(..., description="User password")


class AuthResponse(BaseModel):
    message: str
    user_id: str
    username: str
    role: str
    access_token: str


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: datetime


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
    count_query = select(func.count(User.id))
    result = await db.execute(count_query)
    user_count = result.scalar_one_or_none() or 0

    if user_count > 0:
        raise SetupForbiddenError(
            message="Owner account already initialized. The setup endpoint is permanently disabled."
        )

    provided_token = req.setup_token or x_setup_token
    if not provided_token or not secrets.compare_digest(
        provided_token.strip(), settings.SETUP_TOKEN.strip()
    ):
        raise InvalidSetupTokenError(
            message="Invalid or missing setup token. Provide the one-time token from your terminal/env."
        )

    hashed_pw = hash_password(req.password)
    owner = User(
        username=req.username.strip().lower(),
        password_hash=hashed_pw,
        role="owner",
    )
    db.add(owner)

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


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    """
    Owner login with username-keyed rate limiting and exponential backoff.
    Sets httpOnly session cookies.
    """
    service = AuthService(db, settings)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    access_token, refresh_token, user = await service.authenticate_user(
        username=req.username,
        password=req.password,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    AuthService.set_auth_cookies(
        response=response,
        access_token=access_token,
        refresh_token=refresh_token,
        access_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )

    return AuthResponse(
        message="Login successful.",
        user_id=user.id,
        username=user.username,
        role=user.role,
        access_token=access_token,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_tokens(
    request: Request,
    response: Response,
    niko_refresh_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    """
    Rotate session refresh token with automatic reuse detection.
    """
    token = niko_refresh_token or request.headers.get("X-Refresh-Token")
    if not token:
        from backend.app.core.exceptions import AuthenticationError
        raise AuthenticationError("Refresh token missing.")

    service = AuthService(db, settings)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    new_access_token, new_refresh_token, user = await service.refresh_session(
        raw_refresh_token=token,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    AuthService.set_auth_cookies(
        response=response,
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        access_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )

    return AuthResponse(
        message="Session refreshed successfully.",
        user_id=user.id,
        username=user.username,
        role=user.role,
        access_token=new_access_token,
    )


@router.post("/logout")
async def logout(
    response: Response,
    niko_refresh_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Revoke current session and clear cookies."""
    service = AuthService(db, settings)
    await service.logout(niko_refresh_token)
    AuthService.clear_auth_cookies(response)
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return currently authenticated user profile."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        created_at=current_user.created_at,
    )
