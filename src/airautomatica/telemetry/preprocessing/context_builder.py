"""LLM context builder: deterministic, capped payload."""

import math

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.preprocessing.feature_engine import FeatureSet
from airautomatica.telemetry.preprocessing.models import (
    LlmContextPayload,
    TelemetryEvent,
)

# Fixed key order for deterministic serialization
TOP_METRICS_KEYS = (
    "voltage_v",
    "rel_alt_m",
    "groundspeed_m_s",
    "distance_to_home_m",
    "estimated_endurance_s",
)

# Event names for trend prioritization (higher index = higher priority in sentence)
_EVENT_PRIORITY = (
    "gps_degraded",
    "battery_sag",
    "weak_return_margin",
    "unstable_attitude",
    "altitude_loss",
    "high_power_draw",
    "heading_drift",
    "mission_progress_stall",
)


def _valid_float(x: float | None) -> bool:
    return x is not None and isinstance(x, (int, float)) and not math.isnan(x)


def _power_label(watts: float | None) -> str:
    if not _valid_float(watts):
        return ""
    if watts > 150:
        return "high power draw"
    if watts > 80:
        return "moderate power draw"
    return "low power draw"


def _build_trend_sentence(
    phase: str,
    mode: str,
    features: FeatureSet,
    current: AircraftState | None,
    events: list[TelemetryEvent],
) -> str:
    """One operator-focused trend sentence. Phase + top events + key metrics."""
    phase_label = phase.replace("_", " ").title()
    if phase in ("rtl", "landing", "loiter"):
        base = f"{phase_label} active"
    elif phase in ("cruise", "climb", "descent", "takeoff"):
        base = f"{phase_label} flight"
    elif phase == "disarmed":
        base = phase_label
    else:
        base = phase_label

    extras: list[str] = []
    event_names = [e.name for e in events]
    top_events = sorted(
        event_names,
        key=lambda n: _EVENT_PRIORITY.index(n) if n in _EVENT_PRIORITY else 99,
    )[:2]
    if top_events:
        ev_str = " and ".join(e.replace("_", " ") for e in top_events)
        extras.append(ev_str)

    power = _power_label(features.watts)
    if power and not any("power" in e for e in extras):
        extras.append(power)

    if _valid_float(features.distance_to_home_m):
        d = features.distance_to_home_m
        if d >= 1000:
            extras.append(f"{d / 1000:.1f} km from home")
        else:
            extras.append(f"{int(d)} m from home")

    if extras:
        return f"{base} with {', '.join(extras)}."
    return f"{base}."


def build_llm_context(
    phase: str,
    mode: str,
    events: list[TelemetryEvent],
    features: FeatureSet,
    current: AircraftState | None,
) -> LlmContextPayload:
    """Build capped, deterministic payload. Endurance only when confidence >= medium."""
    top_events: tuple[dict, ...] = ()
    for e in events[:3]:
        top_events += (
            {"name": e.name, "severity": e.severity, "evidence": e.evidence},
        )
    while len(top_events) < 3:
        top_events += ({"name": "", "severity": "info", "evidence": {}},)
    top_events = top_events[:3]

    metrics: dict[str, float] = {}
    if current:
        if _valid_float(current.voltage_v):
            metrics["voltage_v"] = float(current.voltage_v)
        if _valid_float(current.rel_alt_m):
            metrics["rel_alt_m"] = float(current.rel_alt_m)
        if _valid_float(current.groundspeed_m_s):
            metrics["groundspeed_m_s"] = float(current.groundspeed_m_s)
    if _valid_float(features.distance_to_home_m):
        metrics["distance_to_home_m"] = float(features.distance_to_home_m)
    if features.endurance_confidence in ("medium", "high") and _valid_float(
        features.estimated_endurance_s
    ):
        metrics["estimated_endurance_s"] = float(features.estimated_endurance_s)
    else:
        metrics["estimated_endurance_s"] = -1.0  # sentinel: unavailable

    top_metrics = {k: metrics.get(k, 0.0) for k in TOP_METRICS_KEYS}
    top_metrics = dict(list(top_metrics.items())[:5])

    trend = _build_trend_sentence(phase, mode, features, current, events)

    return LlmContextPayload(
        phase=phase,
        mode=mode,
        top_events=top_events,
        top_metrics=top_metrics,
        trend_summary=trend,
    )
