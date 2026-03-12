"""Debrief engine: post-flight/session summaries from recorded telemetry."""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.preprocessing.event_engine import EventEngine
from airautomatica.telemetry.preprocessing.feature_engine import FeatureEngine
from airautomatica.telemetry.preprocessing.flight_phase_engine import FlightPhaseEngine
from airautomatica.telemetry.preprocessing.rolling_buffer import (
    RollingWindowBuffer,
    create_buffers,
)

if TYPE_CHECKING:
    from airautomatica.services.persistence import PersistenceService


def _valid(x: float | None) -> bool:
    return x is not None and isinstance(x, (int, float)) and not math.isnan(x)


def _sample_to_state(
    sample: dict,
    home_lat: float | None,
    home_lon: float | None,
    climb_rate_m_s: float = 0.0,
) -> AircraftState:
    """Convert debrief sample dict to AircraftState."""
    ts = sample.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    lat = sample.get("lat")
    lon = sample.get("lon")
    if lat is None:
        lat = float("nan")
    if lon is None:
        lon = float("nan")
    v = sample.get("voltage_v")
    i = sample.get("current_a")
    if v is None:
        v = float("nan")
    if i is None:
        i = float("nan")
    gs = sample.get("groundspeed_m_s")
    if gs is None:
        gs = float("nan")
    roll = sample.get("roll_rad")
    pitch = sample.get("pitch_rad")
    yaw = sample.get("yaw_rad")
    hdg = sample.get("heading_deg")
    alt = sample.get("rel_alt_m")
    air = sample.get("airspeed_m_s")
    roll = roll if roll is not None else float("nan")
    pitch = pitch if pitch is not None else float("nan")
    yaw = yaw if yaw is not None else float("nan")
    hdg = hdg if hdg is not None else float("nan")
    alt = alt if alt is not None else float("nan")
    air = air if air is not None else float("nan")
    mode = sample.get("mode") or ""
    connected = sample.get("connected")
    if connected is None:
        connected = True

    return AircraftState(
        connected=bool(connected),
        heartbeat=0,
        mode=mode,
        lat=lat,
        lon=lon,
        rel_alt_m=alt,
        heading_deg=hdg,
        roll_rad=roll,
        pitch_rad=pitch,
        yaw_rad=yaw,
        voltage_v=v,
        current_a=i,
        groundspeed_m_s=gs,
        airspeed_m_s=air,
        timestamp=ts,
        armed=True,
        climb_rate_m_s=climb_rate_m_s,
        home_lat=home_lat,
        home_lon=home_lon,
    )


@dataclass
class DebriefEventStat:
    """Event occurrence stat for debrief."""

    name: str
    count: int
    duration_sec: float


@dataclass
class DebriefSummary:
    """Structured post-flight/session summary."""

    session_id: int
    session_duration_sec: float
    phase_duration_sec: dict[str, float]
    peak_distance_from_home_m: float | None
    average_power_w: float | None
    peak_power_w: float | None
    minimum_voltage_v: float | None
    top_events: list[DebriefEventStat]
    weak_return_margin_occurred: bool
    gps_degraded_occurred: bool
    unstable_attitude_occurred: bool
    assessment_tags: list[str]


def _derive_climb_rate(prev: dict | None, curr: dict) -> float:
    """Derive climb rate from consecutive samples."""
    if prev is None:
        return 0.0
    alt_prev = prev.get("rel_alt_m")
    alt_curr = curr.get("rel_alt_m")
    ts_prev = prev.get("timestamp")
    ts_curr = curr.get("timestamp")
    if not _valid(alt_prev) or not _valid(alt_curr):
        return 0.0
    if ts_prev is None or ts_curr is None:
        return 0.0
    if isinstance(ts_prev, str):
        ts_prev = datetime.fromisoformat(ts_prev.replace("Z", "+00:00"))
    if isinstance(ts_curr, str):
        ts_curr = datetime.fromisoformat(ts_curr.replace("Z", "+00:00"))
    dt = (ts_curr - ts_prev).total_seconds()
    if dt <= 0:
        return 0.0
    return (alt_curr - alt_prev) / dt


class DebriefEngine:
    """Generates structured post-flight summaries from recorded telemetry."""

    def __init__(
        self,
        short_maxlen: int = 20,
        medium_maxlen: int = 100,
        long_maxlen: int = 300,
    ) -> None:
        self._short_maxlen = short_maxlen
        self._medium_maxlen = medium_maxlen
        self._long_maxlen = long_maxlen

    def generate(
        self,
        session_id: int,
        persistence: "PersistenceService",
        sample_limit: int = 10000,
    ) -> DebriefSummary | None:
        """Generate debrief from stored telemetry. Returns None if no samples."""
        samples = persistence.get_session_telemetry_for_debrief(
            session_id, limit=sample_limit
        )
        if not samples:
            return None

        buffers = create_buffers(
            short_maxlen=self._short_maxlen,
            medium_maxlen=self._medium_maxlen,
            long_maxlen=self._long_maxlen,
        )
        feature_engine = FeatureEngine()
        event_engine = EventEngine()
        phase_engine = FlightPhaseEngine()

        home_lat: float | None = None
        home_lon: float | None = None
        first_lat = samples[0].get("lat")
        first_lon = samples[0].get("lon")
        if _valid(first_lat) and _valid(first_lon):
            home_lat = float(first_lat)
            home_lon = float(first_lon)

        phase_duration_sec: dict[str, float] = {}
        event_active_samples: dict[str, int] = {}
        event_occurred: dict[str, bool] = {}
        powers: list[float] = []
        voltages: list[float] = []
        distances: list[float] = []

        prev_sample: dict | None = None
        prev_ts: datetime | None = None

        for sample in samples:
            climb = _derive_climb_rate(prev_sample, sample)
            state = _sample_to_state(sample, home_lat, home_lon, climb)
            for buf in buffers.values():
                buf.append(state)

            features = feature_engine.compute(buffers, state)
            phase = phase_engine.classify(state, features)
            events = event_engine.evaluate(features, state, now=state.timestamp)

            ts = state.timestamp
            dt = 1.0
            if prev_ts is not None:
                dt = (ts - prev_ts).total_seconds()
                if dt <= 0 or dt > 10:
                    dt = 1.0

            phase_duration_sec[phase] = phase_duration_sec.get(phase, 0.0) + dt

            for e in events:
                event_active_samples[e.name] = (
                    event_active_samples.get(e.name, 0.0) + dt
                )
                event_occurred[e.name] = True

            if _valid(features.watts):
                powers.append(features.watts)
            if _valid(state.voltage_v):
                voltages.append(state.voltage_v)
            if _valid(features.distance_to_home_m):
                distances.append(features.distance_to_home_m)

            prev_sample = sample
            prev_ts = ts

        session_duration = sum(phase_duration_sec.values())
        if session_duration <= 0 and samples:
            t0 = samples[0].get("timestamp")
            t1 = samples[-1].get("timestamp")
            if t0 and t1:
                if isinstance(t0, str):
                    t0 = datetime.fromisoformat(t0.replace("Z", "+00:00"))
                if isinstance(t1, str):
                    t1 = datetime.fromisoformat(t1.replace("Z", "+00:00"))
                session_duration = (t1 - t0).total_seconds()

        top_events = [
            DebriefEventStat(
                name=k,
                count=1 if event_occurred.get(k, False) else 0,
                duration_sec=float(v),
            )
            for k, v in sorted(
                event_active_samples.items(),
                key=lambda x: (-x[1], x[0]),
            )[:10]
        ]

        peak_dist = max(distances) if distances else None
        avg_power = sum(powers) / len(powers) if powers else None
        peak_power = max(powers) if powers else None
        min_voltage = min(voltages) if voltages else None

        tags = _compute_assessment_tags(
            weak_return=event_occurred.get("weak_return_margin", False),
            gps_degraded=event_occurred.get("gps_degraded", False),
            unstable=event_occurred.get("unstable_attitude", False),
            power_hungry=bool(peak_power and peak_power > 150),
            min_v=min_voltage,
        )

        return DebriefSummary(
            session_id=session_id,
            session_duration_sec=session_duration,
            phase_duration_sec=phase_duration_sec,
            peak_distance_from_home_m=peak_dist,
            average_power_w=avg_power,
            peak_power_w=peak_power,
            minimum_voltage_v=min_voltage,
            top_events=top_events,
            weak_return_margin_occurred=event_occurred.get("weak_return_margin", False),
            gps_degraded_occurred=event_occurred.get("gps_degraded", False),
            unstable_attitude_occurred=event_occurred.get("unstable_attitude", False),
            assessment_tags=tags,
        )


@dataclass
class CompactDebriefPayload:
    """Compact payload for local Llama. Fixed shape, deterministic."""

    total_duration_sec: float
    dominant_phase: str
    top_3_event_summaries: tuple[str, ...]  # exactly 3
    top_5_metrics: tuple[tuple[str, float], ...]  # exactly 5 (key, value)
    assessment_sentence: str

    def to_dict(self) -> dict:
        return {
            "total_duration_sec": self.total_duration_sec,
            "dominant_phase": self.dominant_phase,
            "top_3_event_summaries": list(self.top_3_event_summaries),
            "top_5_metrics": dict(self.top_5_metrics) if self.top_5_metrics else {},
            "assessment_sentence": self.assessment_sentence,
        }


def build_compact_debrief_context(summary: DebriefSummary) -> CompactDebriefPayload:
    """Build compact payload for local Llama. Small, deterministic."""
    dominant = ""
    if summary.phase_duration_sec:
        dominant = max(
            summary.phase_duration_sec.items(),
            key=lambda x: x[1],
        )[0]

    event_summaries: list[str] = []
    for e in summary.top_events[:3]:
        if e.duration_sec > 0:
            event_summaries.append(f"{e.name}: {e.duration_sec:.0f}s")
        else:
            event_summaries.append(e.name or "")
    while len(event_summaries) < 3:
        event_summaries.append("")

    metrics: list[tuple[str, float]] = []
    if summary.session_duration_sec is not None:
        metrics.append(("duration_sec", summary.session_duration_sec))
    if summary.peak_distance_from_home_m is not None:
        metrics.append(("peak_distance_m", summary.peak_distance_from_home_m))
    if summary.average_power_w is not None:
        metrics.append(("avg_power_w", summary.average_power_w))
    if summary.peak_power_w is not None:
        metrics.append(("peak_power_w", summary.peak_power_w))
    if summary.minimum_voltage_v is not None:
        metrics.append(("min_voltage_v", summary.minimum_voltage_v))
    while len(metrics) < 5:
        metrics.append(("", 0.0))
    metrics = metrics[:5]

    tags = summary.assessment_tags or []
    if tags:
        sentence = f"Assessment: {', '.join(tags)}."
    else:
        sentence = "Assessment: stable."
    if summary.session_duration_sec and summary.session_duration_sec > 0:
        mins = int(summary.session_duration_sec / 60)
        sentence = f"{mins} min flight. {sentence}"

    return CompactDebriefPayload(
        total_duration_sec=summary.session_duration_sec,
        dominant_phase=dominant,
        top_3_event_summaries=tuple(event_summaries[:3]),
        top_5_metrics=tuple(metrics[:5]),
        assessment_sentence=sentence,
    )


def _compute_assessment_tags(
    weak_return: bool,
    gps_degraded: bool,
    unstable: bool,
    power_hungry: bool,
    min_v: float | None,
) -> list[str]:
    """Compute deterministic assessment tags."""
    tags: list[str] = []
    if not weak_return and not gps_degraded and not unstable and not power_hungry:
        tags.append("stable")
    if power_hungry:
        tags.append("power_hungry")
    if weak_return:
        tags.append("return_risk")
    if gps_degraded:
        tags.append("gps_limited")
    if unstable:
        tags.append("attitude_unstable")
    if min_v is not None and min_v < 11.0:
        tags.append("battery_concern")
    return tags
