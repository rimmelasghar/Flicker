"""Global token-bucket rate limit for the phone API."""

import time
from collections.abc import Callable

# A person flicks at most about one photo per second; allow bursts (a
# stack of photos, page reloads) but cap sustained traffic.
BURST = 60
PER_SECOND = 2.0


class RateLimiter:
    """Token bucket shared by all clients (requests come through Docker's
    gateway, so per-client limits would not work anyway)."""

    def __init__(
        self,
        burst: int = BURST,
        per_second: float = PER_SECOND,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._burst = burst
        self._rate = per_second
        self._clock = clock
        self._tokens = float(burst)
        self._last = clock()

    def allow(self) -> bool:
        now = self._clock()
        self._tokens = min(self._burst, self._tokens + (now - self._last) * self._rate)
        self._last = now
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False

    def retry_after(self) -> int:
        """Whole seconds until the next request would be allowed."""
        missing = max(0.0, 1 - self._tokens)
        return max(1, int(missing / self._rate + 0.999)) if self._rate else 60
