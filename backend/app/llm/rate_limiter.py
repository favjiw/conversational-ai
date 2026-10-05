"""Token-bucket rate limiter with async support.

Used to stay within Gemini free-tier rate limits. Limits are configurable
per model since different models may have different quotas.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """Async token-bucket rate limiter.

    Args:
        requests_per_minute: Maximum requests allowed per minute.
        name: Human-readable name for logging (e.g., model ID).
    """

    def __init__(self, requests_per_minute: int = 15, name: str = "default"):
        self.rate = requests_per_minute
        self.name = name
        self._tokens = float(requests_per_minute)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Wait until a token is available and consume it.

        Returns:
            The number of seconds waited (0 if no wait was needed).
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            # Refill tokens based on time elapsed
            self._tokens = min(
                self.rate,
                self._tokens + elapsed * (self.rate / 60.0),
            )
            self._last_refill = now

            if self._tokens < 1.0:
                wait_sec = (1.0 - self._tokens) / (self.rate / 60.0)
                logger.info(
                    "Rate limiter '%s': throttling for %.2fs",
                    self.name,
                    wait_sec,
                )
                await asyncio.sleep(wait_sec)
                self._tokens = 0.0
                return wait_sec
            else:
                self._tokens -= 1.0
                return 0.0

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (approximate)."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        return min(
            self.rate,
            self._tokens + elapsed * (self.rate / 60.0),
        )


class RateLimiterRegistry:
    """Manages per-model rate limiters.

    Usage:
        registry = RateLimiterRegistry(default_rpm=15)
        limiter = registry.get("gemini-2.0-flash")
        await limiter.acquire()
    """

    def __init__(self, default_rpm: int = 15):
        self._default_rpm = default_rpm
        self._limiters: dict[str, RateLimiter] = {}
        self._overrides: dict[str, int] = {}

    def set_limit(self, model: str, rpm: int) -> None:
        """Override RPM for a specific model."""
        self._overrides[model] = rpm
        if model in self._limiters:
            self._limiters[model] = RateLimiter(rpm, name=model)

    def get(self, model: str) -> RateLimiter:
        """Get or create a rate limiter for a model."""
        if model not in self._limiters:
            rpm = self._overrides.get(model, self._default_rpm)
            self._limiters[model] = RateLimiter(rpm, name=model)
        return self._limiters[model]
