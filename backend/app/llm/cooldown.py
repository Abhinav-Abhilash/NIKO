import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.llm.defaults import DEFAULT_PROVIDER_LIMITS, VERIFIED_RATE_LIMITS
from backend.app.llm.types import ProviderRateLimit

logger = get_logger("niko.llm.cooldown")


class QuotaWindow:
    """Tracks rolling minute and daily quota metrics in memory with thread safety."""

    def __init__(self, key: tuple[str, str]):
        self.key = key  # (provider, model)
        # Store tuples of (timestamp, token_count) for the rolling 60-second window
        self.minute_records: deque[tuple[float, int]] = deque()
        self.current_day_str: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.daily_requests: int = 0
        self.daily_tokens: int = 0
        # Active forced cooldown (e.g. from upstream 429 or predictive exhaustion)
        self.cooldown_until: float = 0.0
        self.cooldown_reason: str | None = None

    def _prune_minute(self, now: float) -> None:
        threshold = now - 60.0
        while self.minute_records and self.minute_records[0][0] < threshold:
            self.minute_records.popleft()

    def _check_day_rollover(self, now_dt: datetime) -> None:
        day_str = now_dt.strftime("%Y-%m-%d")
        if day_str != self.current_day_str:
            self.current_day_str = day_str
            self.daily_requests = 0
            self.daily_tokens = 0

    def record_usage(self, now: float, tokens: int) -> None:
        self._prune_minute(now)
        now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
        self._check_day_rollover(now_dt)

        self.minute_records.append((now, tokens))
        self.daily_requests += 1
        self.daily_tokens += tokens

    def get_current_usage(self, now: float) -> dict[str, int]:
        self._prune_minute(now)
        now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
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
    """

    def __init__(self, predictive_threshold_ratio: float = 0.90):
        self.predictive_threshold_ratio = predictive_threshold_ratio
        self._lock = threading.RLock()
        self._windows: dict[tuple[str, str], QuotaWindow] = {}

    def _get_window(self, provider: str, model: str) -> QuotaWindow:
        key = (provider.lower(), model.lower())
        if key not in self._windows:
            self._windows[key] = QuotaWindow(key)
        return self._windows[key]

    def get_limits(self, provider: str, model: str) -> ProviderRateLimit:
        key = (provider.lower(), model.lower())
        if key in VERIFIED_RATE_LIMITS:
            return VERIFIED_RATE_LIMITS[key]
        if provider.lower() in DEFAULT_PROVIDER_LIMITS:
            return DEFAULT_PROVIDER_LIMITS[provider.lower()]
        return ProviderRateLimit(
            rpm=15, rpd=1000, tpm=6000, tpd=100_000, source="Fallback Default"
        )

    def is_cooled_down(
        self, provider: str, model: str, now: float | None = None
    ) -> tuple[bool, str | None, float]:
        """
        Check if a provider/model is currently in cooldown (either predictive or from a 429).
        Returns: (is_cooled_down, reason_str, seconds_remaining)
        """
        if now is None:
            now = time.time()

        with self._lock:
            window = self._get_window(provider, model)

            # 1. Check existing forced cooldown
            if now < window.cooldown_until:
                remaining = window.cooldown_until - now
                return True, window.cooldown_reason, remaining

            # 2. Check predictive limits
            limits = self.get_limits(provider, model)
            usage = window.get_current_usage(now)

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

            # Predictive check for RPD
            if limits.rpd > 0 and usage["daily_requests"] >= int(
                limits.rpd * self.predictive_threshold_ratio
            ):
                # Cooldown until UTC midnight
                now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
                remaining = max(1.0, 86400.0 - (now_dt.hour * 3600 + now_dt.minute * 60 + now_dt.second))
                reason = f"Predictive RPD threshold reached ({usage['daily_requests']}/{limits.rpd})"
                window.cooldown_until = now + remaining
                window.cooldown_reason = reason
                logger.warning(
                    "Predictive cooldown engaged for RPD",
                    provider=provider,
                    model=model,
                    usage=usage["daily_requests"],
                    limit=limits.rpd,
                )
                return True, reason, remaining

            # Predictive check for TPD
            if limits.tpd > 0 and usage["daily_tokens"] >= int(
                limits.tpd * self.predictive_threshold_ratio
            ):
                now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
                remaining = max(1.0, 86400.0 - (now_dt.hour * 3600 + now_dt.minute * 60 + now_dt.second))
                reason = f"Predictive TPD threshold reached ({usage['daily_tokens']}/{limits.tpd})"
                window.cooldown_until = now + remaining
                window.cooldown_reason = reason
                logger.warning(
                    "Predictive cooldown engaged for TPD",
                    provider=provider,
                    model=model,
                    usage=usage["daily_tokens"],
                    limit=limits.tpd,
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
        headers or using default fallback backoff.
        """
        if now is None:
            now = time.time()

        cooldown_secs = retry_after_seconds
        if headers:
            # Check standard Retry-After header
            retry_header = headers.get("retry-after") or headers.get("Retry-After")
            if retry_header:
                try:
                    cooldown_secs = float(retry_header)
                except ValueError:
                    pass

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
        """Get summary status of all tracked models and quotas."""
        if now is None:
            now = time.time()
        results: list[dict[str, Any]] = []
        with self._lock:
            for (provider, model), window in self._windows.items():
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
        self, targets: list[Any], now: float | None = None
    ) -> float:
        """Calculate the shortest remaining cooldown in seconds across a list of targets."""
        if now is None:
            now = time.time()
        remaining_times: list[float] = []
        for t in targets:
            provider = getattr(t, "provider", None) if not isinstance(t, dict) else t.get("provider")
            model = getattr(t, "model", None) if not isinstance(t, dict) else t.get("model")
            if provider and model:
                is_cooled, _, remaining = self.is_cooled_down(str(provider), str(model), now=now)
                if is_cooled and remaining > 0:
                    remaining_times.append(remaining)
        if remaining_times:
            return min(remaining_times)
        return 0.0


# Global singleton tracker
cooldown_tracker = PredictiveCooldownTracker()

