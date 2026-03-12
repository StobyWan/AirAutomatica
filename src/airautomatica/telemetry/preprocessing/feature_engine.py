"""Feature engine: deterministic features from rolling buffers."""

import math
from dataclasses import dataclass
from typing import Literal

from airautomatica.models.state import AircraftState, nan_to_none
from airautomatica.telemetry.preprocessing.rolling_buffer import RollingWindowBuffer


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two lat/lon points."""
    R = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing from (lat1,lon1) to (lat2,lon2) in degrees."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        dlam
    )
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _valid(x: float) -> bool:
    return isinstance(x, (int, float)) and not math.isnan(x)


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    valid = [v for v in values if _valid(v)]
    if len(valid) < 2:
        return 0.0
    mean = sum(valid) / len(valid)
    return sum((v - mean) ** 2 for v in valid) / (len(valid) - 1)


def _linear_trend(values: list[float]) -> float:
    """Slope per sample (not per second). Simple linear regression."""
    valid = [(i, v) for i, v in enumerate(values) if _valid(v)]
    if len(valid) < 2:
        return 0.0
    n = len(valid)
    sum_x = sum(x for x, _ in valid)
    sum_y = sum(y for _, y in valid)
    sum_xy = sum(x * y for x, y in valid)
    sum_xx = sum(x * x for x, _ in valid)
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-12:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


@dataclass
class FeatureSet:
    """First-pass features. Use None for unavailable."""

    roll_var: float | None
    pitch_var: float | None
    heading_change_rate_deg_s: float | None
    altitude_rate_m_s: float | None
    voltage_trend: float | None
    current_trend: float | None
    watts: float | None
    distance_to_home_m: float | None
    home_bearing_deg: float | None
    relative_bearing_deg: float | None
    estimated_endurance_s: float | None
    endurance_confidence: Literal["low", "medium", "high"]
    return_margin_s: float | None
    groundspeed_mean_medium: float | None  # Mean groundspeed over medium buffer


class FeatureEngine:
    """Computes features from buffers and current state."""

    def __init__(
        self,
        voltage_min_v: float = 10.5,
        endurance_stable_samples: int = 5,
    ) -> None:
        self._voltage_min = voltage_min_v
        self._endurance_stable = endurance_stable_samples

    def compute(
        self,
        buffers: dict[str, RollingWindowBuffer[AircraftState]],
        current: AircraftState | None,
    ) -> FeatureSet:
        short = buffers.get("short", RollingWindowBuffer(maxlen=0))
        medium = buffers.get("medium", RollingWindowBuffer(maxlen=0))
        samples = short.get_samples()

        roll_var = pitch_var = None
        if samples:
            rolls = [s.roll_rad for s in samples]
            pitches = [s.pitch_rad for s in samples]
            roll_var = _variance(rolls) if rolls else None
            pitch_var = _variance(pitches) if pitches else None

        heading_change_rate = None
        if len(samples) >= 2:
            headings = [s.heading_deg for s in samples if _valid(s.heading_deg)]
            if len(headings) >= 2:
                dt = (samples[-1].timestamp - samples[0].timestamp).total_seconds()
                if dt > 0:
                    delta = (headings[-1] - headings[0] + 360) % 360
                    if delta > 180:
                        delta -= 360
                    heading_change_rate = delta / dt

        altitude_rate = None
        if current and _valid(current.climb_rate_m_s):
            altitude_rate = current.climb_rate_m_s

        voltage_trend = current_trend = groundspeed_mean_medium = None
        if medium:
            med = medium.get_samples()
            if med:
                voltage_trend = _linear_trend([s.voltage_v for s in med])
                current_trend = _linear_trend([s.current_a for s in med])
                gs = [s.groundspeed_m_s for s in med if _valid(s.groundspeed_m_s)]
                if gs:
                    groundspeed_mean_medium = sum(gs) / len(gs)

        watts = None
        if current and _valid(current.voltage_v) and _valid(current.current_a):
            watts = current.voltage_v * current.current_a

        distance_to_home_m = home_bearing_deg = relative_bearing_deg = None
        if current and _valid(current.lat) and _valid(current.lon):
            lat, lon = current.lat, current.lon
            home_lat = nan_to_none(current.home_lat)
            home_lon = nan_to_none(current.home_lon)
            if home_lat is not None and home_lon is not None:
                distance_to_home_m = _haversine_m(lat, lon, home_lat, home_lon)
                home_bearing_deg = _bearing_deg(lat, lon, home_lat, home_lon)
                if _valid(current.heading_deg):
                    rel = (home_bearing_deg - current.heading_deg + 360) % 360
                    if rel > 180:
                        rel -= 360
                    relative_bearing_deg = rel

        estimated_endurance_s = None
        endurance_confidence: Literal["low", "medium", "high"] = "low"
        if current and _valid(current.voltage_v) and _valid(current.current_a):
            v = current.voltage_v
            i = max(current.current_a, 0.1)
            if v > self._voltage_min:
                estimated_endurance_s = (v - self._voltage_min) * 3600 / i
            if medium and len(medium.get_samples()) >= self._endurance_stable:
                endurance_confidence = "medium"
            if estimated_endurance_s is None:
                endurance_confidence = "low"

        return_margin_s = None
        if (
            current
            and estimated_endurance_s is not None
            and endurance_confidence in ("medium", "high")
            and distance_to_home_m is not None
            and _valid(current.groundspeed_m_s)
            and current.groundspeed_m_s > 0.5
        ):
            time_to_home = distance_to_home_m / current.groundspeed_m_s
            return_margin_s = estimated_endurance_s - time_to_home

        return FeatureSet(
            roll_var=roll_var,
            pitch_var=pitch_var,
            heading_change_rate_deg_s=heading_change_rate,
            altitude_rate_m_s=altitude_rate,
            voltage_trend=voltage_trend,
            current_trend=current_trend,
            watts=watts,
            distance_to_home_m=distance_to_home_m,
            home_bearing_deg=home_bearing_deg,
            relative_bearing_deg=relative_bearing_deg,
            estimated_endurance_s=estimated_endurance_s,
            endurance_confidence=endurance_confidence,
            return_margin_s=return_margin_s,
            groundspeed_mean_medium=groundspeed_mean_medium,
        )
