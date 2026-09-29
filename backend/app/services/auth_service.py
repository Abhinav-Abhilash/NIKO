import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import AuthenticationError, RateLimitExceededError
from backend.app.core.logging import get_logger
from backend.app.core.security import (
    create_jwt_token,
    hash_token,
    verify_password,
)
from backend.app.db.models import User
from backend.app.repositories.session_repository import SessionRepository
from backend.app.repositories.user_repository import UserRepository

logger = get_logger("auth_service")


class LoginRateLimiter:
    """
    In-memory rate limiter keyed on username with exponential backoff.
    Prevents localhost IP lockout while stopping brute-force password guessing.
    Throttles registered and unknown/unregistered usernames identically.
    """

    MAX_BACKOFF_SECONDS: float = 60.0
    MAX_ENTRIES: int = 5000
    BACKOFF_SCHEDULE: dict[int, float] = {
        4: 2.0,
        5: 5.0,
        6: 15.0,
    }

    def __init__(self, reset_seconds: int = 300, max_entries: int = 5000) -> None:
        self.reset_seconds = reset_seconds
        self.max_entries = max_entries
        self._history: dict[str, dict[str, float]] = {}

    def _evict_if_needed(self, now: float) -> None:
        """Evict expired entries or oldest records when history reaches maximum capacity."""
        if len(self._history) < self.max_entries:
            return

        # 1. Purge entries where reset_seconds has elapsed
        expired_keys = [
            k for k, v in self._history.items() if now - v["last_failed"] > self.reset_seconds
        ]
        for k in expired_keys:
            del self._history[k]

        # 2. If still at or over capacity, evict oldest by last_failed timestamp
        if len(self._history) >= self.max_entries:
            overflow = len(self._history) - self.max_entries + 1
            sorted_keys = sorted(
                self._history.keys(), key=lambda k: self._history[k]["last_failed"]
            )
            for k in sorted_keys[:overflow]:
                del self._history[k]

    def get_lockout_remaining(self, username: str) -> float:
        now = time.time()
        record = self._history.get(username)
        if not record:
            return 0.0
        locked_until = record.get("locked_until", 0.0)
        return max(0.0, locked_until - now)

    def check_limit(self, username: str) -> None:
        now = time.time()
        record = self._history.get(username)
        if not record:
            return

        # Check if previous window expired
        if now - record["last_failed"] > self.reset_seconds:
            del self._history[username]
            return

        locked_until = record.get("locked_until", 0)
        if now < locked_until:
            remaining = int(locked_until - now) + 1
            raise RateLimitExceededError(
                f"Too many failed login attempts for '{username}'. Please wait {remaining} seconds."
            )

    def record_failure(self, username: str) -> None:
        now = time.time()
        self._evict_if_needed(now)
        record = self._history.get(username, {"attempts": 0.0, "last_failed": now, "locked_until": 0.0})
        attempts = int(record["attempts"]) + 1

        # Exponential backoff schedule capped at MAX_BACKOFF_SECONDS:
        # Attempts 1-3: no delay
        # 4: 2s delay | 5: 5s delay | 6: 15s delay | 7+: capped at 60s
        if attempts >= 7:
            backoff_delay = self.MAX_BACKOFF_SECONDS
        else:
            backoff_delay = self.BACKOFF_SCHEDULE.get(attempts, 0.0)

        self._history[username] = {
            "attempts": float(attempts),
            "last_failed": now,
            "locked_until": now + backoff_delay,
        }
        logger.warning(
            "Failed login attempt recorded",
            username=username,
            attempts=attempts,
            backoff=backoff_delay,
            cap=self.MAX_BACKOFF_SECONDS,
        )

    def record_success(self, username: str) -> None:
        self._history.pop(username, None)


# Module-level rate limiter singleton
login_limiter = LoginRateLimiter()


class AuthService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)

    async def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, User]:
        """
        Authenticate user with username-keyed exponential backoff rate limiting.
        Returns: (access_token, raw_refresh_token, user)
        """
        clean_user = username.strip().lower()
        login_limiter.check_limit(clean_user)

        user = await self.user_repo.get_by_username(clean_user)
        if not user or not verify_password(password, user.password_hash):
            login_limiter.record_failure(clean_user)
            raise AuthenticationError("Invalid username or password.")

        # Success: reset backoff tracker
        login_limiter.record_success(clean_user)

        # Issue token pair
        family_id = str(uuid.uuid4())
        access_token = create_jwt_token(
            payload={"sub": user.id, "username": user.username, "role": user.role},
            secret_key=self.settings.JWT_SECRET_KEY,
            algorithm=self.settings.JWT_ALGORITHM,
            expires_delta=timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        raw_refresh_token = str(uuid.uuid4()) + str(uuid.uuid4())
        refresh_hash = hash_token(raw_refresh_token)
        refresh_expires = datetime.now(UTC) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)

        await self.session_repo.create_session(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            family_id=family_id,
            expires_at=refresh_expires,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.db.commit()

        logger.info("User authenticated successfully", username=user.username, role=user.role)
        return access_token, raw_refresh_token, user

    async def refresh_session(
        self,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, User]:
        """
        Rotate refresh token with automatic token-family reuse detection.
        If a revoked token is presented, all sessions in the family are revoked immediately.
        """
        token_hash = hash_token(raw_refresh_token)
        session = await self.session_repo.get_by_refresh_token_hash(token_hash)

        if not session:
            raise AuthenticationError("Invalid refresh token.")

        # Automatic Reuse Detection
        if session.is_revoked:
            logger.error("Token reuse detected! Revoking entire session family", family_id=session.family_id)
            await self.session_repo.revoke_family(session.family_id)
            await self.db.commit()
            raise AuthenticationError(
                "Revoked refresh token reused. All sessions have been terminated for security."
            )

        if session.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            await self.session_repo.revoke_session(session.id)
            await self.db.commit()
            raise AuthenticationError("Refresh token has expired. Please log in again.")

        user = session.user

        # Rotate tokens: revoke current token and issue replacement within same family
        await self.session_repo.revoke_session(session.id)

        new_access_token = create_jwt_token(
            payload={"sub": user.id, "username": user.username, "role": user.role},
            secret_key=self.settings.JWT_SECRET_KEY,
            algorithm=self.settings.JWT_ALGORITHM,
            expires_delta=timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        new_raw_refresh_token = str(uuid.uuid4()) + str(uuid.uuid4())
        new_refresh_hash = hash_token(new_raw_refresh_token)
        refresh_expires = datetime.now(UTC) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)

        await self.session_repo.create_session(
            user_id=user.id,
            refresh_token_hash=new_refresh_hash,
            family_id=session.family_id,
            expires_at=refresh_expires,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.db.commit()

        logger.info("Session refreshed with token rotation", username=user.username, family_id=session.family_id)
        return new_access_token, new_raw_refresh_token, user

    async def logout(self, raw_refresh_token: str | None) -> None:
        """Revoke the active session."""
        if not raw_refresh_token:
            return

        token_hash = hash_token(raw_refresh_token)
        session = await self.session_repo.get_by_refresh_token_hash(token_hash)
        if session and not session.is_revoked:
            await self.session_repo.revoke_session(session.id)
            await self.db.commit()
            logger.info("Session revoked upon logout", session_id=session.id)

    @staticmethod
    def set_auth_cookies(
        response: Response,
        access_token: str,
        refresh_token: str,
        access_expire_minutes: int = 15,
        refresh_expire_days: int = 7,
    ) -> None:
        """Set secure httpOnly cookies on the HTTP response."""
        response.set_cookie(
            key="niko_access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            secure=False,  # localhost over HTTP
            max_age=access_expire_minutes * 60,
            path="/",
        )
        response.set_cookie(
            key="niko_refresh_token",
            value=refresh_token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=refresh_expire_days * 24 * 3600,
            path="/api/v1/auth",
        )

    @staticmethod
    def clear_auth_cookies(response: Response) -> None:
        """Clear session cookies."""
        response.delete_cookie(key="niko_access_token", path="/")
        response.delete_cookie(key="niko_refresh_token", path="/api/v1/auth")
