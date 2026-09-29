import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import AuthenticationError, RateLimitExceededError
from backend.app.services.auth_service import AuthService, LoginRateLimiter


@pytest.mark.asyncio
async def test_unknown_usernames_are_throttled_with_backoff(db_session: AsyncSession) -> None:
    service = AuthService(db_session)
    limiter = LoginRateLimiter(reset_seconds=60)
    unknown_user = "non_existent_ghost_user_99"

    # 1. First 3 attempts fail with AuthenticationError without lockout
    for _ in range(3):
        limiter.check_limit(unknown_user)
        with pytest.raises(AuthenticationError):
            # authenticate_user with unknown user
            user = await service.user_repo.get_by_username(unknown_user)
            if not user:
                limiter.record_failure(unknown_user)
                raise AuthenticationError("Invalid username or password.")

    # 2. 4th attempt triggers 2s backoff lockout
    limiter.record_failure(unknown_user)
    with pytest.raises(RateLimitExceededError, match="Too many failed login attempts"):
        limiter.check_limit(unknown_user)

    lockout_remaining = limiter.get_lockout_remaining(unknown_user)
    assert 0.0 < lockout_remaining <= 2.0


def test_rate_limiter_backoff_cap() -> None:
    limiter = LoginRateLimiter(reset_seconds=300)
    user = "attacker_target"

    # Simulate 10 consecutive failed attempts
    for _ in range(10):
        limiter.record_failure(user)

    # Lockout must not exceed MAX_BACKOFF_SECONDS (60.0s)
    remaining = limiter.get_lockout_remaining(user)
    assert remaining <= LoginRateLimiter.MAX_BACKOFF_SECONDS
    assert remaining > 55.0  # Just set to 60s
