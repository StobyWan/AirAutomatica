"""Mission logic loop scaffold. Consumes only normalized AircraftState and AiResult.

AI ingestion semantics:
- Mission flow: infer() -> process_result() -> persisted detections. Only labels in
  _ALLOWED_PERCEPTION_LABELS are accepted.
- AI HAT one-shot: separate path, cached only, does not feed mission flow.
- Recording Hailo post-process: overlay only on video; no structured events to mission.
"""

import asyncio
import logging
import math
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from airautomatica.ai.models import AiResult
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState
from airautomatica.services.state_store import StateStore

if TYPE_CHECKING:
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)


def _normalize_label(s: str) -> str:
    """Trim, uppercase, collapse spaces/underscores/hyphens to single underscore."""
    if not s:
        return ""
    t = s.strip().upper()
    for sep in (" ", "-"):
        t = t.replace(sep, "_")
    while "__" in t:
        t = t.replace("__", "_")
    return t.strip("_")


# Placeholder labels (unparseable output, error fallback, mock/scaffold) — not real detections.
# Use normalized forms for comparison.
_PLACEHOLDER_LABELS: frozenset[str] = frozenset(
    {"ERROR", "LMSTUDIO", "OLLAMA", "MOCK_OK", "AIHAT_SCAFFOLD"}
)

# Telemetry/status/UI labels — not perception detections. Reject these.
_DISALLOWED_PERCEPTION_LABELS: frozenset[str] = frozenset(
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
        "HEADING",
        "ALTITUDE",
        "SPEED",
        "GPS",
        "VOLTAGE",
        "UI",
        "BUTTON",
        "LABEL",
        "OVERLAY",
        "DEBUG",
        "TEXT",
    }
)

# Compact real-world perception vocabulary. Labels not in this set are rejected.
_ALLOWED_PERCEPTION_LABELS: frozenset[str] = frozenset(
    {
        "VEHICLE",
        "PERSON",
        "BUILDING",
        "TREE",
        "ROAD",
        "OBSTACLE",
        "AIRCRAFT",
        "TOWER",
        "POLE",
        "TARGET",
        "GROUND_VEHICLE",
        "WATER",
        "STRUCTURE",
        "NONE",
    }
)

_PERCEPTION_COUNTS: dict[str, int] = defaultdict(int)


def get_perception_counts() -> dict[str, int]:
    """Return copy of outcome counters for observability."""
    return {
        "accepted": _PERCEPTION_COUNTS["accepted"],
        "suppressed": _PERCEPTION_COUNTS["suppressed"],
        "no_detection": _PERCEPTION_COUNTS["no_detection"],
        "non_perception_label": _PERCEPTION_COUNTS["non_perception_label"],
        "unknown_label": _PERCEPTION_COUNTS["unknown_label"],
        "parse_error": _PERCEPTION_COUNTS["parse_error"],
    }


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
        session_ref: Optional[list[int | None]] = None,
        min_confidence: float = 0.5,
        duplicate_window_sec: float = 30.0,
    ) -> None:
        self._store = store
        self._ai_service = ai_service
        self._interval = interval_sec
        self._ai_interval = ai_interval_sec
        self._persistence = persistence
        self._session_ref = session_ref or []
        self._min_confidence = min_confidence
        self._duplicate_window_sec = duplicate_window_sec
        self._last_ai_time: float = 0.0
        self._last_accepted: dict[str, float] = {}

    def set_ai_service(self, ai_service: Optional["AiService"]) -> None:
        """Replace the AI service at runtime. Used by AI subsystem hot-reload."""
        self._ai_service = ai_service

    def reconfigure(
        self,
        min_confidence: Optional[float] = None,
        duplicate_window_sec: Optional[float] = None,
    ) -> None:
        """Update min_confidence and/or duplicate_window_sec at runtime.
        Safe to call from settings handler; values take effect on next process_result.
        """
        if min_confidence is not None:
            self._min_confidence = max(0.0, min(1.0, min_confidence))
        if duplicate_window_sec is not None:
            self._duplicate_window_sec = max(0.0, duplicate_window_sec)

    def _get_ignore_reason(self, result: AiResult) -> str:
        """Reason why a result was ignored. Empty string means accept."""
        norm = _normalize_label(result.label or "")
        if norm == "":
            return "no_response"
        if norm in _PLACEHOLDER_LABELS:
            return "placeholder_label"
        if norm == "NONE":
            return "no_detection"
        if norm in _DISALLOWED_PERCEPTION_LABELS:
            return "non_perception_label"
        if norm not in _ALLOWED_PERCEPTION_LABELS:
            return "unknown_label"
        if result.confidence < self._min_confidence:
            return "low_confidence"
        summary = (result.summary or "").strip()
        if not summary:
            return "empty_summary"
        if summary == "No response":
            return "no_response"
        if result.metadata is not None and result.metadata.get("raw_length") == 0:
            return "raw_length_zero"
        return ""

    def _is_meaningful(self, result: AiResult) -> bool:
        """True if result is worth acting on or persisting."""
        return self._get_ignore_reason(result) == ""

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
            if reason == "placeholder_label":
                _PERCEPTION_COUNTS["parse_error"] += 1
            elif reason == "no_detection":
                _PERCEPTION_COUNTS["no_detection"] += 1
            elif reason == "non_perception_label":
                _PERCEPTION_COUNTS["non_perception_label"] += 1
            elif reason == "unknown_label":
                _PERCEPTION_COUNTS["unknown_label"] += 1
            suffix = ""
            if reason == "placeholder_label":
                norm = _normalize_label(result.label or "")
                if norm in ("MOCK_OK", "AIHAT_SCAFFOLD"):
                    suffix = " (mock/scaffold fallback)"
            logger.debug(
                "ai ignored: reason=%s label=%s%s", reason, result.label, suffix
            )
            return
        if self._is_duplicate(result):
            _PERCEPTION_COUNTS["suppressed"] += 1
            now = time.monotonic()
            ago = now - self._last_accepted.get(result.label, now)
            logger.debug(
                "ai suppressed: label=%s (seen %.0fs ago)",
                result.label,
                ago,
            )
            return
        _PERCEPTION_COUNTS["accepted"] += 1
        logger.info(
            "ai accepted: label=%s confidence=%.2f",
            result.label,
            result.confidence,
        )
        session_id = self._session_ref[0] if self._session_ref else None
        if self._persistence is not None and session_id is not None:
            self._persistence.insert_detection(
                session_id,
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

            session_id = self._session_ref[0] if self._session_ref else None
            if (
                self._ai_service is not None
                and state is not None
                and session_id is not None
            ):
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
