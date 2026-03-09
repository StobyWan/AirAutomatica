"""Aircraft state model."""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

TelemetryStatus = Literal["starting", "connecting", "connected", "stale", "disconnected", "backoff"]


def nan_to_none(x: float | None) -> float | None:
    """Convert NaN or None to None for JSON/DB. Reused by API and persistence."""
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    return x


@dataclass(frozen=True)
class AircraftState:
    """Immutable snapshot of aircraft telemetry state."""

    connected: bool
    heartbeat: int
    mode: str
    lat: float
    lon: float
    rel_alt_m: float
    heading_deg: float
    roll_rad: float
    pitch_rad: float
    yaw_rad: float
    voltage_v: float
    current_a: float
    groundspeed_m_s: float
    airspeed_m_s: float
    timestamp: datetime
    last_heartbeat_at: Optional[datetime] = None
    heartbeat_age_s: float = 0.0
    telemetry_status: TelemetryStatus = "connected"
    reconnect_count: int = 0
    last_disconnect_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize for API response. NaN values become None for JSON."""
        return {
            "connected": self.connected,
            "heartbeat": self.heartbeat,
            "telemetry_status": self.telemetry_status,
            "reconnect_count": self.reconnect_count,
            "last_disconnect_reason": self.last_disconnect_reason,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None,
            "heartbeat_age_s": nan_to_none(self.heartbeat_age_s),
            "mode": self.mode,
            "lat": nan_to_none(self.lat),
            "lon": nan_to_none(self.lon),
            "rel_alt_m": nan_to_none(self.rel_alt_m),
            "heading_deg": nan_to_none(self.heading_deg),
            "roll_rad": nan_to_none(self.roll_rad),
            "pitch_rad": nan_to_none(self.pitch_rad),
            "yaw_rad": nan_to_none(self.yaw_rad),
            "voltage_v": nan_to_none(self.voltage_v),
            "current_a": nan_to_none(self.current_a),
            "groundspeed_m_s": nan_to_none(self.groundspeed_m_s),
            "airspeed_m_s": nan_to_none(self.airspeed_m_s),
            "timestamp": self.timestamp.isoformat(),
        }
