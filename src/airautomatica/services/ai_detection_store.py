"""In-memory store for last successful AI detection result."""

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airautomatica.ai.detection_models import DetectionResult


@dataclass
class CachedDetection:
    """Cached AI detection result with timestamp and optional session link."""

    result: "DetectionResult"
    timestamp: datetime
    summary: str | None = None
    source: str = "camera"
    session_id: int | None = None


class AiDetectionStore:
    """Thread-safe store for last successful AI detection.

    Overwrites cache only when state is 'ready' or 'no_detections'.
    Does not overwrite a good cached result with transient errors.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cached: CachedDetection | None = None

    def get_last_detection(self) -> CachedDetection | None:
        """Return last successful detection, or None if never run successfully."""
        with self._lock:
            return self._cached

    def set_last_detection(
        self,
        result: "DetectionResult",
        summary: str | None = None,
        source: str = "camera",
        session_id: int | None = None,
    ) -> None:
        """Store result only when state is ready or no_detections."""
        if result.state not in ("ready", "no_detections"):
            return
        with self._lock:
            self._cached = CachedDetection(
                result=result,
                timestamp=datetime.now(timezone.utc),
                summary=summary,
                source=source,
                session_id=session_id,
            )
