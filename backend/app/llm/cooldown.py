import contextlib
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.llm.defaults import DEFAULT_PROVIDER_LIMITS, VERIFIED_RATE_LIMITS
from backend.app.llm.types import ProviderRateLimit

logger = get_logger("niko.llm.cooldown")

PACIFIC_TZ: tzinfo
try:
    from zoneinfo import ZoneInfo
    PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
except Exception:
    # Safe timezone fallback on Windows environments without tzdata package
    PACIFIC_TZ = timezone(timedelta(hours=-7), name="Pacific")

# Models with low daily quota that maintain a reserved pool for hard tasks
DEFAULT_RESERVE_PER_MODEL: dict[tuple[str, str], int] = {
    ("gemini", "gemini-3.8-flash"): 4,
    ("gemini", "gemini-3.7-flash"): 4,
    ("gemini", "gemini-3.5-flash"): 4,
    ("gemini", "gemini-flash-latest"): 4,
}


def get_pacific_now(ts: float | None = None) -> datetime:
    """Return datetime in America/Los_Angeles timezone (Midnight Pacific resets)."""
    if ts is not None:
        return datetime.fromtimestamp(ts, tz=PACIFIC_TZ)
    return datetime.now(PACIFIC_TZ)


class QuotaWindow:
    """Tracks rolling minute and daily quota metrics in memory with thread safety."""

    def __init__(self, key: tuple[str, str], reserve_requests: int = 0):
        self.key = key  # (provider, model)
        # Store tuples of (timestamp, token_count) for the rolling 60-second window
        self.minute_records: deque[tuple[float, int]] = deque()
        self.current_day_str: str = get_pacific_now().strftime("%Y-%m-%d")
        self.daily_requests: int = 0
        self.daily_tokens: int = 0
        self.reserve_requests: int = reserve_requests
        # Active forced cooldown (e.g. from upstream 429 or predictive exhaustion)
        self.cooldown_until: float = 0.0
        self.cooldown_reason: str | None = None

    def _prune_minute(self, now: float) -> None:
        threshold = now - 60.0
        while self.minute_records and self.minute_records[0][0] < threshold:
            self.minute_records.popleft()

    def _check_day_rollover(self, now_dt_pacific: datetime) -> None:
        day_str = now_dt_pacific.strftime("%Y-%m-%d")
        if day_str != self.current_day_str:
            self.current_day_str = day_str
            self.daily_requests = 0
            self.daily_tokens = 0
            # Reset daily exhaustion cooldown if active
            if self.cooldown_reason and "Daily" in self.cooldown_reason:
                self.cooldown_until = 0.0
                self.cooldown_reason = None

    def record_usage(self, now: float, tokens: int) -> None:
        self._prune_minute(now)
        now_dt = get_pacific_now(now)
        self._check_day_rollover(now_dt)

        self.minute_records.append((now, tokens))
        self.daily_requests += 1
        self.daily_tokens += tokens

    def get_current_usage(self, now: float) -> dict[str, int]:
        self._prune_minute(now)
        now_dt = get_pacific_now(now)
        self._check_day_rollover(now_dt)

        minute_reqs = len(self.minute_records)
        minute_toks = sum(t[1] for t in self.minute_records)
        return {
            "minute_requests": minute_reqs,
            "minute_tokens": minute_toks,
            "daily_requests": self.daily_requests,
            "daily_tokens": self.daily_tokens,
        }


class PredictiveCooldownTracker:
    """
    Monitors usage and upstream response codes to initiate cooldowns BEFORE
    rate limits are exceeded, or when 429 errors are received.
    Enforces per-model daily counters (Midnight Pacific reset) and reserved pools for hard tasks.
    """

    def __init__(self, predictive_threshold_ratio: float = 0.90):
        self.predictive_threshold_ratio = predictive_threshold_ratio
        self._lock = threading.RLock()
        self._windows: dict[tuple[str, str], QuotaWindow] = {}
        self._custom_reserves: dict[tuple[str, str], int] = {}

    def reset(self) -> None:
        """Reset all tracking state across all windows."""
        with self._lock:
            self._windows.clear()
            self._custom_reserves.clear()

    def _get_window(self, provider: str, model: str) -> QuotaWindow:
        key = (provider.lower(), model.lower())
        if key not in self._windows:
            reserve = self._custom_reserves.get(key, DEFAULT_RESERVE_PER_MODEL.get(key, 0))
            self._windows[key] = QuotaWindow(key, reserve_requests=reserve)
        return self._windows[key]

    def set_model_reserve(self, provider: str, model: str, reserve_requests: int) -> None:
        key = (provider.lower(), model.lower())
        with self._lock:
            self._custom_reserves[key] = reserve_requests
            if key in self._windows:
                self._windows[key].reserve_requests = reserve_requests

    def get_limits(self, provider: str, model: str) -> ProviderRateLimit:
        key = (provider.lower(), model.lower())
        if key in VERIFIED_RATE_LIMITS:
            return VERIFIED_RATE_LIMITS[key]
        if provider.lower() in DEFAULT_PROVIDER_LIMITS:
            return DEFAULT_PROVIDER_LIMITS[provider.lower()]
        return ProviderRateLimit(
            rpm=15, rpd=500, tpm=250_000, tpd=0, source="Fallback Default"
        )

    def _seconds_until_pacific_midnight(self, now: float) -> float:
        now_dt = get_pacific_now(now)
        next_midnight = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1.0, (next_midnight - now_dt).total_seconds())

    def is_cooled_down(
        self,
        provider: str,
        model: str,
        is_hard_task: bool = False,
        now: float | None = None,
    ) -> tuple[bool, str | None, float]:
        """
        Check if a provider/model is currently in cooldown (either predictive or from a 429).
        If daily usage enters the reserve pool, non-hard tasks are gated while hard tasks proceed.
        Returns: (is_cooled_down, reason_str, seconds_remaining)
        """
        if now is None:
            now = time.time()

        with self._lock:
            window = self._get_window(provider, model)

            # 1. Check existing forced cooldown (e.g. 429 or previous exhaustion)
            if now < window.cooldown_until:
                remaining = window.cooldown_until - now
                return True, window.cooldown_reason, remaining

            # 2. Check predictive limits
            limits = self.get_limits(provider, model)
            usage = window.get_current_usage(now)

            # Check dead models (0 RPM/RPD)
            if limits.rpm == 0 or limits.rpd == 0:
                return True, f"Model {model} is deprecated/dead (0 quota)", 86400.0

            # Daily Limit and Reserve Checks (Midnight Pacific reset)
            if limits.rpd > 0:
                # Full RPD exhaustion
                if usage["daily_requests"] >= limits.rpd:
                    remaining = self._seconds_until_pacific_midnight(now)
                    reason = f"Daily RPD limit reached ({usage['daily_requests']}/{limits.rpd})"
                    window.cooldown_until = now + remaining
                    window.cooldown_reason = reason
                    logger.warning(
                        "Daily RPD limit reached",
                        provider=provider,
                        model=model,
                        usage=usage["daily_requests"],
                        limit=limits.rpd,
                    )
                    return True, reason, remaining

                # Reserve check for non-hard tasks
                effective_limit = max(1, limits.rpd - window.reserve_requests)
                if not is_hard_task and window.reserve_requests > 0 and usage["daily_requests"] >= effective_limit:
                    remaining = self._seconds_until_pacific_midnight(now)
                    reason = (
                        f"Daily reserve threshold reached ({usage['daily_requests']}/{limits.rpd}, "
                        f"reserve={window.reserve_requests}) reserved strictly for hard tasks"
                    )
                    return True, reason, remaining

            # Predictive check for RPM
            if limits.rpm > 0 and usage["minute_requests"] >= int(
                limits.rpm * self.predictive_threshold_ratio
            ):
                remaining = 60.0
                reason = f"Predictive RPM threshold reached ({usage['minute_requests']}/{limits.rpm})"
                window.cooldown_until = now + remaining
                window.cooldown_reason = reason
                logger.warning(
                    "Predictive cooldown engaged for RPM",
                    provider=provider,
                    model=model,
                    usage=usage["minute_requests"],
                    limit=limits.rpm,
                )
                return True, reason, remaining

            # Predictive check for TPM
            if limits.tpm > 0 and usage["minute_tokens"] >= int(
                limits.tpm * self.predictive_threshold_ratio
            ):
                remaining = 60.0
                reason = f"Predictive TPM threshold reached ({usage['minute_tokens']}/{limits.tpm})"
                window.cooldown_until = now + remaining
                window.cooldown_reason = reason
                logger.warning(
                    "Predictive cooldown engaged for TPM",
                    provider=provider,
                    model=model,
                    usage=usage["minute_tokens"],
                    limit=limits.tpm,
                )
                return True, reason, remaining

            return False, None, 0.0

    def record_success(
        self, provider: str, model: str, input_tokens: int, output_tokens: int, now: float | None = None
    ) -> None:
        """Record successful request and token usage."""
        if now is None:
            now = time.time()
        total_tokens = max(1, input_tokens + output_tokens)
        with self._lock:
            window = self._get_window(provider, model)
            window.record_usage(now, total_tokens)

    def record_429(
        self,
        provider: str,
        model: str,
        retry_after_seconds: float = 60.0,
        headers: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> float:
        """
        Record real upstream 429 Too Many Requests response, extracting retry-after
        headers or using default fallback backoff. Always trusted over local counters.
        """
        if now is None:
            now = time.time()

        cooldown_secs = retry_after_seconds
        if headers:
            retry_header = headers.get("retry-after") or headers.get("Retry-After")
            if retry_header:
                with contextlib.suppress(ValueError):
                    cooldown_secs = float(retry_header)

        cooldown_secs = max(5.0, cooldown_secs)
        with self._lock:
            window = self._get_window(provider, model)
            window.cooldown_until = now + cooldown_secs
            window.cooldown_reason = f"Upstream 429 Too Many Requests (backoff {cooldown_secs:.1f}s)"
            logger.warning(
                "Upstream 429 backoff recorded",
                provider=provider,
                model=model,
                cooldown_seconds=cooldown_secs,
            )
        return cooldown_secs

    def get_status(self, now: float | None = None) -> list[dict[str, Any]]:
        """Get summary status of all tracked models and quotas including daily counters and reserves."""
        if now is None:
            now = time.time()
        results: list[dict[str, Any]] = []
        with self._lock:
            # Include all verified rate limits so uncalled models still display quotas
            all_keys = set(self._windows.keys()).union(VERIFIED_RATE_LIMITS.keys())
            for provider, model in sorted(all_keys):
                window = self._get_window(provider, model)
                usage = window.get_current_usage(now)
                limits = self.get_limits(provider, model)
                is_cooled = now < window.cooldown_until
                results.append(
                    {
                        "provider": provider,
                        "model": model,
                        "is_cooled_down": is_cooled,
                        "cooldown_reason": window.cooldown_reason if is_cooled else None,
                        "cooldown_remaining_seconds": max(0.0, window.cooldown_until - now) if is_cooled else 0.0,
                        "usage": usage,
                        "daily_requests": usage["daily_requests"],
                        "daily_limit": limits.rpd,
                        "reserve_requests": window.reserve_requests,
                        "limits": {
                            "rpm": limits.rpm,
                            "rpd": limits.rpd,
                            "tpm": limits.tpm,
                            "tpd": limits.tpd,
                        },
                    }
                )
        return results

    def get_shortest_cooldown_for_targets(
        self, targets: list[Any], is_hard_task: bool = False, now: float | None = None
    ) -> float:
        """Calculate the shortest remaining cooldown in seconds across a list of targets."""
        if now is None:
            now = time.time()
        remaining_times: list[float] = []
        for t in targets:
            provider = getattr(t, "provider", None) if not isinstance(t, dict) else t.get("provider")
            model = getattr(t, "model", None) if not isinstance(t, dict) else t.get("model")
            if provider and model:
                is_cooled, _, remaining = self.is_cooled_down(str(provider), str(model), is_hard_task=is_hard_task, now=now)
                if is_cooled and remaining > 0:
                    remaining_times.append(remaining)
        if remaining_times:
            return min(remaining_times)
        return 0.0


# Global singleton tracker
cooldown_tracker = PredictiveCooldownTracker()
