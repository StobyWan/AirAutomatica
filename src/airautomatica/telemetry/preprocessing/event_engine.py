"""Event engine: rule-based events with hysteresis."""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, TypeGuard

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.preprocessing.feature_engine import FeatureSet
from airautomatica.telemetry.preprocessing.models import TelemetryEvent


def _valid(x: Any) -> TypeGuard[float]:
    return x is not None and isinstance(x, (int, float)) and not math.isnan(x)


@dataclass
class _EventState:
    """Per-event hysteresis state."""

    open_count: int = 0
    clear_count: int = 0
    started_at: datetime | None = None
    is_open: bool = False
    last_evidence: dict = field(default_factory=dict)


# Thresholds (tunable)
GPS_SATS_MIN = 6
GPS_FIX_3D = 3
VOLTAGE_SAG_V = 11.0
VOLTAGE_TREND_SAG = -0.15
POWER_HIGH_W = 150.0
ATTITUDE_VAR_THRESH = 0.05
ALTITUDE_LOSS_RATE = -3.0
RETURN_MARGIN_MIN_S = 60.0
HEADING_DRIFT_RATE_DEG_S = 15.0  # deg/s sustained = drift
MISSION_STALL_SPEED_M_S = 0.5
MISSION_MODES = frozenset({"AUTO", "GUIDED"})
HYSTERESIS_OPEN = 3
HYSTERESIS_CLEAR = 3


class EventEngine:
    """Rule-based events with open/clear hysteresis."""

    def __init__(
        self,
        open_samples: int = HYSTERESIS_OPEN,
        clear_samples: int = HYSTERESIS_CLEAR,
    ) -> None:
        self._open_samples = open_samples
        self._clear_samples = clear_samples
        self._states: dict[str, _EventState] = {}

    def _get_state(self, name: str) -> _EventState:
        if name not in self._states:
            self._states[name] = _EventState()
        return self._states[name]

    def _check_gps_degraded(
        self, current: AircraftState | None, now: datetime
    ) -> tuple[bool, dict] | None:
        if not current:
            return None
        sats = current.satellites_visible
        fix = current.gps_fix_type
        degraded = (sats is not None and sats < GPS_SATS_MIN) or (
            fix is not None and fix < GPS_FIX_3D
        )
        evidence = {"satellites_visible": sats or 0, "gps_fix_type": fix or 0}
        return (degraded, evidence)

    def _check_battery_sag(
        self, current: AircraftState | None, features: FeatureSet, now: datetime
    ) -> tuple[bool, dict] | None:
        if not current:
            return None
        v = current.voltage_v
        trend = features.voltage_trend
        sag = (_valid(v) and v < VOLTAGE_SAG_V) or (
            _valid(trend) and trend < VOLTAGE_TREND_SAG
        )
        evidence = {"voltage_v": v if _valid(v) else 0, "voltage_trend": trend or 0}
        return (sag, evidence)

    def _check_high_power_draw(
        self, features: FeatureSet, now: datetime
    ) -> tuple[bool, dict] | None:
        w = features.watts
        high = _valid(w) and w > POWER_HIGH_W
        evidence = {"watts": w if _valid(w) else 0}
        return (high, evidence)

    def _check_unstable_attitude(
        self, features: FeatureSet, now: datetime
    ) -> tuple[bool, dict] | None:
        rv = features.roll_var
        pv = features.pitch_var
        unstable = (_valid(rv) and rv > ATTITUDE_VAR_THRESH) or (
            _valid(pv) and pv > ATTITUDE_VAR_THRESH
        )
        evidence = {"roll_var": rv or 0, "pitch_var": pv or 0}
        return (unstable, evidence)

    def _check_altitude_loss(
        self, features: FeatureSet, now: datetime
    ) -> tuple[bool, dict] | None:
        rate = features.altitude_rate_m_s
        loss = _valid(rate) and rate < ALTITUDE_LOSS_RATE
        evidence = {"altitude_rate_m_s": rate if _valid(rate) else 0}
        return (loss, evidence)

    def _check_weak_return_margin(
        self, features: FeatureSet, now: datetime
    ) -> tuple[bool, dict] | None:
        margin = features.return_margin_s
        weak = _valid(margin) and margin < RETURN_MARGIN_MIN_S
        evidence = {"return_margin_s": margin if _valid(margin) else 0}
        return (weak, evidence)

    def _check_heading_drift(
        self, features: FeatureSet, now: datetime
    ) -> tuple[bool, dict] | None:
        rate = features.heading_change_rate_deg_s
        drift = _valid(rate) and abs(rate) > HEADING_DRIFT_RATE_DEG_S
        evidence = {"heading_change_rate_deg_s": rate if _valid(rate) else 0}
        return (drift, evidence)

    def _check_mission_progress_stall(
        self,
        current: AircraftState | None,
        features: FeatureSet,
        now: datetime,
    ) -> tuple[bool, dict] | None:
        if not current:
            return None
        mode = (current.mode or "").upper()
        if mode not in MISSION_MODES:
            return None
        gs_mean = features.groundspeed_mean_medium
        stall = _valid(gs_mean) and gs_mean < MISSION_STALL_SPEED_M_S
        evidence = {
            "groundspeed_mean_medium": gs_mean if _valid(gs_mean) else 0,
            "mode": mode,
        }
        return (stall, evidence)

    def evaluate(
        self,
        features: FeatureSet,
        current: AircraftState | None,
        now: datetime | None = None,
    ) -> list[TelemetryEvent]:
        now = now or datetime.now(timezone.utc)
        events: list[TelemetryEvent] = []

        check_list: list[
            tuple[
                str,
                Literal["info", "warn", "error", "critical"],
                tuple[bool, dict] | None,
            ]
        ] = [
            ("gps_degraded", "warn", self._check_gps_degraded(current, now)),
            ("battery_sag", "warn", self._check_battery_sag(current, features, now)),
            ("high_power_draw", "warn", self._check_high_power_draw(features, now)),
            ("unstable_attitude", "warn", self._check_unstable_attitude(features, now)),
            ("altitude_loss", "warn", self._check_altitude_loss(features, now)),
            (
                "weak_return_margin",
                "warn",
                self._check_weak_return_margin(features, now),
            ),
            ("heading_drift", "info", self._check_heading_drift(features, now)),
            (
                "mission_progress_stall",
                "info",
                self._check_mission_progress_stall(current, features, now),
            ),
        ]

        for name, severity, result in check_list:
            st = self._get_state(name)
            if result is None:
                if st.is_open:
                    st.clear_count += 1
                    if st.clear_count >= self._clear_samples:
                        st.is_open = False
                        st.open_count = 0
                else:
                    st.clear_count = 0
                continue

            triggered, evidence = result
            st.last_evidence = evidence

            if triggered:
                st.clear_count = 0
                st.open_count += 1
                if st.open_count >= self._open_samples and not st.is_open:
                    st.is_open = True
                    st.started_at = now
            else:
                if st.is_open:
                    st.clear_count += 1
                    if st.clear_count >= self._clear_samples:
                        st.is_open = False
                        st.open_count = 0
                else:
                    st.open_count = 0

        for name, severity, _ in check_list:
            st = self._get_state(name)
            if st.is_open and st.started_at:
                events.append(
                    TelemetryEvent(
                        name=name,
                        severity=severity,
                        started_at=st.started_at,
                        ended_at=None,
                        evidence=st.last_evidence,
                        operator_hint=None,
                    )
                )

        return events
