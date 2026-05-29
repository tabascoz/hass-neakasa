from dataclasses import dataclass, field
from datetime import timedelta, datetime, timezone
import logging
from typing import Optional, Any, Awaitable, Callable

_LOGGER = logging.getLogger(__name__)

class ValueCacher:
    def __init__(self, refresh_after: Optional[timedelta], discard_after: Optional[timedelta]):
        self._refresh_after = refresh_after
        self._discard_after = discard_after
        self._manually_marked_stale = False
        self._value: Optional[Any] = None
        self._last_update: Optional[datetime] = None
        # concurrency
        import asyncio
        self._lock = asyncio.Lock()
        self._inflight = None  # asyncio.Task | None

    def set(self, value: Any) -> None:
        self._value = value
        self._last_update = datetime.now(timezone.utc)
        self._manually_marked_stale = False

    def clear(self) -> None:
        self._value = None
        self._last_update = None
        self._manually_marked_stale = False

    def mark_as_stale(self) -> None:
        self._manually_marked_stale = True

    def value_if_not_stale(self) -> Optional[Any]:
        if self._manually_marked_stale or self._value is None or self._last_update is None:
            return None
        if self._refresh_after is not None:
            if self._refresh_after <= timedelta(0):
                return None
            if datetime.now(timezone.utc) - self._last_update > self._refresh_after:
                return None
        return self._value

    def value_if_not_discarded(self) -> Optional[Any]:
        if self._value is None or self._last_update is None:
            return None
        if self._discard_after is not None:
            if self._discard_after <= timedelta(0):
                return None
            if datetime.now(timezone.utc) - self._last_update > self._discard_after:
                return None
        return self._value

    async def get_or_update(self, update_func: Callable[[], Awaitable[Any]]) -> Any:
        # fast path
        current = self.value_if_not_stale()
        if current is not None:
            return current

        async with self._lock:
            # re-check under lock
            current = self.value_if_not_stale()
            if current is not None:
                return current

            if self._inflight is not None:
                try:
                    return await self._inflight
                except Exception as err:
                    fallback = self.value_if_not_discarded()
                    if fallback is not None:
                        return fallback
                    raise

            loop = __import__("asyncio").get_running_loop()
            self._inflight = loop.create_task(update_func())
            try:
                result = await self._inflight
                self.set(result)
                return result
            except Exception as err:
                fallback = self.value_if_not_discarded()
                if fallback is not None:
                    return fallback
                raise
            finally:
                self._inflight = None
