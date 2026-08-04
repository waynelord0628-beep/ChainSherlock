import asyncio
from time import monotonic


class AsyncRateLimiter:
    def __init__(self, requests_per_second: float = 5.0) -> None:
        self.minimum_interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            remaining = self.minimum_interval - (monotonic() - self._last_request)
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request = monotonic()
