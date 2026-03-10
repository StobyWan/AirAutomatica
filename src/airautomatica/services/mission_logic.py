"""Mission logic loop scaffold. Consumes only normalized AircraftState and AiResult."""

import asyncio
import logging
import math
import time
from typing import TYPE_CHECKING, Optional

from airautomatica.ai.models import AiResult
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState
from airautomatica.services.state_store import StateStore

if TYPE_CHECKING:
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)

# Generic placeholder labels (LM Studio best-effort, error fallback) — not real detections.
_PLACEHOLDER_LABELS: frozenset[str] = frozenset({"error", "lmstudio"})

# Mode/status/system labels — not perception detections. Reject these. (Uppercase for case-insensitive check.)
_NON_PERCEPTION_LABELS: frozenset[str] = frozenset(
    {
        "GUIDED",
        "AUTO",
        "LOITER",
        "RTL",
        "QLOITER",
        "QRTL",
        "STABILIZE",
        "UNKNOWN",
        "DEVICE_STATUS",
        "BATTERY",
        "TELEMETRY",
        "STATE",
        "MODE",
    }
)


def _fmt(x: float, fmt: str = "%.1f") -> str:
    """Format float, or 'N/A' if NaN."""
    if isinstance(x, float) and math.isnan(x):
        return "N/A"
    return fmt % x


class MissionLogic:
    """Basic mission logic. Uses only AircraftState and AiResult—backend-agnostic."""

    def __init__(
        self,
        store: StateStore,
        ai_service: Optional[AiService] = None,
        interval_sec: float = 2.0,
        ai_interval_sec: float = 10.0,
        persistence: Optional["PersistenceService"] = None,
        session_id: Optional[int] = None,
        min_confidence: float = 0.5,
        duplicate_window_sec: float = 30.0,
    ) -> None:
        self._store = store
        self._ai_service = ai_service
        self._interval = interval_sec
        self._ai_interval = ai_interval_sec
        self._persistence = persistence
        self._session_id = session_id
        self._min_confidence = min_confidence
        self._duplicate_window_sec = duplicate_window_sec
        self._last_ai_time: float = 0.0
        self._last_accepted: dict[str, float] = {}

    def _is_meaningful(self, result: AiResult) -> bool:
        """True if result is worth acting on or persisting."""
        if result.label in _PLACEHOLDER_LABELS:
            return False
        if result.confidence < self._min_confidence:
            return False
        summary = (result.summary or "").strip()
        if not summary or summary == "No response":
            return False
        if result.metadata is not None and result.metadata.get("raw_length") == 0:
            return False
        if (result.label or "").strip().upper() in _NON_PERCEPTION_LABELS:
            return False
        return True

    def _get_ignore_reason(self, result: AiResult) -> str:
        """Reason why a result was ignored."""
        if result.label in _PLACEHOLDER_LABELS:
            return "placeholder_label"
        if result.confidence < self._min_confidence:
            return "low_confidence"
        summary = (result.summary or "").strip()
        if not summary:
            return "empty_summary"
        if summary == "No response":
            return "no_response"
        if result.metadata is not None and result.metadata.get("raw_length") == 0:
            return "raw_length_zero"
        if (result.label or "").strip().upper() in _NON_PERCEPTION_LABELS:
            return "non_perception_label"
        return "unknown"

    def _is_duplicate(self, result: AiResult) -> bool:
        """True if same label was accepted recently."""
        now = time.monotonic()
        self._last_accepted = {
            k: v
            for k, v in self._last_accepted.items()
            if now - v < self._duplicate_window_sec
        }
        return result.label in self._last_accepted

    def _record_accepted(self, result: AiResult) -> None:
        """Record that a detection was accepted."""
        self._last_accepted[result.label] = time.monotonic()

    def process_result(
        self,
        state: AircraftState,
        result: AiResult,
    ) -> None:
        """Filter, dedupe, log, and persist. Call after infer()."""
        if not self._is_meaningful(result):
            reason = self._get_ignore_reason(result)
            logger.debug(
                "ai ignored: reason=%s label=%s confidence=%.2f",
                reason,
                result.label,
                result.confidence,
            )
            return
        if self._is_duplicate(result):
            now = time.monotonic()
            ago = now - self._last_accepted.get(result.label, now)
            logger.debug(
                "ai suppressed: label=%s (seen %.0fs ago)",
                result.label,
                ago,
            )
            return
        logger.info(
            "ai accepted: label=%s confidence=%.2f",
            result.label,
            result.confidence,
        )
        if self._persistence is not None and self._session_id is not None:
            self._persistence.insert_detection(
                self._session_id,
                result,
                state.lat,
                state.lon,
                state.rel_alt_m,
            )
        self._record_accepted(result)

    async def run(self) -> None:
        """Run mission logic loop indefinitely."""
        while True:
            state = self._store.get()
            self._log_status(state)

            if self._ai_service is not None and state is not None:
                now = time.monotonic()
                if now - self._last_ai_time >= self._ai_interval:
                    self._last_ai_time = now
                    try:
                        result = await self._ai_service.infer(state)
                        self.process_result(state, result)
                    except Exception as e:
                        logger.exception("AI inference failed, continuing: %s", e)

            await asyncio.sleep(self._interval)

    def _log_status(self, state: Optional[AircraftState]) -> None:
        """Log current status from state."""
        if state is None:
            logger.debug("No state yet")
            return
        logger.info(
            "state: connected=%s mode=%s alt=%s hdg=%s bat=%sV",
            state.connected,
            state.mode,
            _fmt(state.rel_alt_m),
            _fmt(state.heading_deg, "%.0f"),
            _fmt(state.voltage_v),
        )
