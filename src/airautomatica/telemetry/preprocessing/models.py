"""Preprocessing models. Phase 1: minimal types for scaffolding."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


class FlightPhase(str, Enum):
    """Deterministic flight phase. Rule-based classifier (Phase 2)."""

    DISARMED = "disarmed"
    TAKEOFF = "takeoff"
    CLIMB = "climb"
    CRUISE = "cruise"
    LOITER = "loiter"
    DESCENT = "descent"
    RTL = "rtl"
    LANDING = "landing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TelemetryEvent:
    """Compact rule-based event. EventEngine output (Phase 1+)."""

    name: str
    severity: Literal["info", "warn", "error", "critical"]
    started_at: datetime
    ended_at: datetime | None
    evidence: dict[str, float | str | int]
    operator_hint: str | None


@dataclass(frozen=True)
class LlmContextPayload:
    """Deterministic, capped payload for LLM. Fixed key order for serialization."""

    phase: str
    mode: str
    top_events: tuple[dict, ...]  # exactly 3 (pad with empty if fewer)
    top_metrics: dict[str, float]  # exactly 5 keys, fixed order
    trend_summary: str

    def to_dict(self) -> dict:
        """Serialize for API/LLM. NaN/-1 preserved for JSON."""
        return {
            "phase": self.phase,
            "mode": self.mode,
            "top_events": list(self.top_events),
            "top_metrics": dict(self.top_metrics),
            "trend_summary": self.trend_summary,
        }


@dataclass(frozen=True)
class PreprocessingSummary:
    """Stub summary from preprocessor. Ready for feature/event logic in Phase 1."""

    phase: str
    mode: str
    buffer_sample_count: int
    last_timestamp: datetime | None
