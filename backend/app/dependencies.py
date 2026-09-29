from typing import Annotated

from fastapi import Cookie, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import AuthenticationError, PermissionDeniedError
from backend.app.core.security import decode_jwt_token
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.repositories.user_repository import UserRepository


async def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    niko_access_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """
    Extract and authenticate the active user from httpOnly cookie or Authorization header.
    """
    token: str | None = None
    if niko_access_token:
        token = niko_access_token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    if not token:
        raise AuthenticationError("Authentication credentials missing. Please log in.")

    payload = decode_jwt_token(
        token=token,
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid authentication token payload.")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise AuthenticationError("Authenticated user no longer exists.")

    return user


async def get_current_owner(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure the user possesses the owner role."""
    if current_user.role != "owner":
        raise PermissionDeniedError("Only the system owner may perform this action.")
    return current_user
