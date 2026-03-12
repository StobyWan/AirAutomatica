"""Lightweight rolling window storage using deque. No pandas."""

from collections import deque
from datetime import datetime, timezone
from typing import Generic, TypeVar

from airautomatica.models.state import AircraftState

T = TypeVar("T")


class RollingWindowBuffer(Generic[T]):
    """Generic rolling buffer. Timestamp-aware trimming by max age (seconds)."""

    def __init__(self, maxlen: int, max_age_sec: float | None = None) -> None:
        self._deque: deque[T] = deque(maxlen=maxlen)
        self._max_age_sec = max_age_sec

    def append(self, item: T) -> None:
        if self._max_age_sec is not None and hasattr(item, "timestamp"):
            self._trim_old(item.timestamp)  # type: ignore[attr-defined]
        self._deque.append(item)

    def _trim_old(self, reference: datetime) -> None:
        ref_ts = reference.timestamp()
        while self._deque:
            first = self._deque[0]
            ts = getattr(first, "timestamp", None)
            if ts is None:
                break
            if (ref_ts - ts.timestamp()) <= self._max_age_sec:
                break
            self._deque.popleft()

    def get_samples(self) -> list[T]:
        return list(self._deque)

    def is_ready(self) -> bool:
        return len(self._deque) > 0

    def __len__(self) -> int:
        return len(self._deque)


def create_buffers(
    short_maxlen: int = 20,
    medium_maxlen: int = 100,
    long_maxlen: int = 300,
) -> dict[str, RollingWindowBuffer[AircraftState]]:
    """Create short (~2s), medium (~10s), long (~60s) buffers at ~10 Hz nominal."""
    return {
        "short": RollingWindowBuffer(maxlen=short_maxlen, max_age_sec=2.0),
        "medium": RollingWindowBuffer(maxlen=medium_maxlen, max_age_sec=10.0),
        "long": RollingWindowBuffer(maxlen=long_maxlen, max_age_sec=60.0),
    }
