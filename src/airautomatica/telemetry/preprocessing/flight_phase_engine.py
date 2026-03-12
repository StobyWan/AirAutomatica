"""Flight phase engine: mode-first classification with hysteresis."""

import math
from dataclasses import dataclass

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.preprocessing.feature_engine import FeatureSet
from airautomatica.telemetry.preprocessing.models import FlightPhase


def _valid(x: float) -> bool:
    return isinstance(x, (int, float)) and not math.isnan(x)


# Modes that map directly to phases (authoritative)
_MODE_RTL = frozenset({"RTL"})
_MODE_LOITER = frozenset({"LOITER", "CIRCLE"})
_MODE_LANDING = frozenset({"QLAND", "AUTOLAND"})
_MODE_TAKEOFF = frozenset({"TAKEOFF"})
# Generic modes: use motion/altitude inference
_MODE_GENERIC = frozenset({"AUTO", "GUIDED", "FBWA", "FBWB", "CRUISE", "STABILIZE"})


@dataclass
class _PhaseState:
    """Hysteresis state for phase transitions."""

    current: str = FlightPhase.UNKNOWN.value
    candidate: str = FlightPhase.UNKNOWN.value
    hold_count: int = 0


class FlightPhaseEngine:
    """Mode-first flight phase classifier with hysteresis."""

    def __init__(self, hold_samples: int = 3) -> None:
        self._hold_samples = hold_samples
        self._state = _PhaseState()

    def classify(
        self,
        current: AircraftState | None,
        features: FeatureSet | None,
    ) -> str:
        """Return phase string. Hysteresis on transitions."""
        raw = self._raw_phase(current, features)
        if raw == self._state.current:
            self._state.candidate = raw
            self._state.hold_count = 0
            return self._state.current
        if raw == self._state.candidate:
            self._state.hold_count += 1
            if self._state.hold_count >= self._hold_samples:
                self._state.current = raw
                self._state.hold_count = 0
            return self._state.current
        self._state.candidate = raw
        self._state.hold_count = 1
        return self._state.current

    def _raw_phase(
        self,
        current: AircraftState | None,
        features: FeatureSet | None,
    ) -> str:
        """Raw phase without hysteresis. Priority: disarmed -> mode -> motion."""
        if not current:
            return FlightPhase.UNKNOWN.value
        if not current.armed:
            return FlightPhase.DISARMED.value
        mode = (current.mode or "").upper()
        if mode in _MODE_RTL:
            return FlightPhase.RTL.value
        if mode in _MODE_LOITER:
            return FlightPhase.LOITER.value
        if mode in _MODE_LANDING:
            return FlightPhase.LANDING.value
        if mode in _MODE_TAKEOFF:
            return FlightPhase.TAKEOFF.value
        if mode in _MODE_GENERIC or mode == "":
            return self._infer_from_motion(current, features)
        return FlightPhase.UNKNOWN.value

    def _infer_from_motion(
        self,
        current: AircraftState,
        features: FeatureSet | None,
    ) -> str:
        """Infer phase from climb_rate, groundspeed when mode is generic."""
        climb = current.climb_rate_m_s if _valid(current.climb_rate_m_s) else 0.0
        speed = current.groundspeed_m_s if _valid(current.groundspeed_m_s) else 0.0
        if climb > 0.5:
            return FlightPhase.CLIMB.value
        if climb < -0.5:
            return FlightPhase.DESCENT.value
        if speed > 2.0:
            return FlightPhase.CRUISE.value
        return FlightPhase.UNKNOWN.value
