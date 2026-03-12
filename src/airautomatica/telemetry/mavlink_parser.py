"""MAVLink message normalization layer for ArduPilot Plane (Matek F405-WING).

Field units and sentinels per mavlink.io common dialect:
- GLOBAL_POSITION_INT (id 33): lat/lon degE7, relative_alt mm, hdg cdeg (65535=invalid)
- ATTITUDE (id 30): roll/pitch/yaw rad
- SYS_STATUS (id 1): voltage_battery mV (65535=invalid), current_battery cA (-1=invalid)
- VFR_HUD (id 74): heading deg, groundspeed/airspeed m/s
- GPS_RAW_INT (id 24): fix_type, satellites_visible
- HOME_POSITION (id 242): latitude, longitude degE7 (ArduPilot)
- GPS_GLOBAL_ORIGIN (id 49): latitude, longitude degE7 (INAV uses for home)
Home messages are read-only; app does not send SET_HOME or equivalent.
"""

import time
from datetime import datetime, timezone
from typing import Any

from airautomatica.models.state import AircraftState, TelemetryStatus

# MAVLink sentinel values
UINT16_MAX = 65535
SYS_STATUS_CURRENT_INVALID = -1

# ArduPilot Plane (APM) flight mode mapping. Source: pymavlink mavutil mode_mapping_apm
MODE_MAPPING_APM: dict[int, str] = {
    0: "MANUAL",
    1: "CIRCLE",
    2: "STABILIZE",
    3: "TRAINING",
    4: "ACRO",
    5: "FBWA",
    6: "FBWB",
    7: "CRUISE",
    8: "AUTOTUNE",
    10: "AUTO",
    11: "RTL",
    12: "LOITER",
    13: "TAKEOFF",
    14: "AVOID_ADSB",
    15: "GUIDED",
    16: "INITIALISING",
    17: "QSTABILIZE",
    18: "QHOVER",
    19: "QLOITER",
    20: "QLAND",
    21: "QRTL",
    22: "QAUTOTUNE",
    23: "QACRO",
    24: "THERMAL",
    25: "LOITERALTQLAND",
    26: "AUTOLAND",
}


def _nan() -> float:
    """Return NaN for unknown numeric values."""
    return float("nan")


class MavlinkNormalizer:
    """Normalizes MAVLink messages into AircraftState. Accumulates state across messages."""

    def __init__(self, heartbeat_timeout_sec: float = 3.0) -> None:
        self._heartbeat_timeout = heartbeat_timeout_sec
        self._heartbeat_count = 0
        self._last_heartbeat_time: float | None = None
        self._last_heartbeat_at: datetime | None = None
        self._mode_mapping: dict[int, str] = dict(MODE_MAPPING_APM)
        self._accum: dict[str, Any] = {
            "mode": "UNKNOWN",
            "armed": False,
            "lat": _nan(),
            "lon": _nan(),
            "rel_alt_m": _nan(),
            "heading_deg": _nan(),
            "roll_rad": _nan(),
            "pitch_rad": _nan(),
            "yaw_rad": _nan(),
            "voltage_v": _nan(),
            "current_a": _nan(),
            "groundspeed_m_s": _nan(),
            "airspeed_m_s": _nan(),
            "climb_rate_m_s": _nan(),
            "gps_fix_type": None,
            "satellites_visible": None,
            "home_lat": None,
            "home_lon": None,
        }

    def apply(self, msg: Any) -> None:
        """Apply message to accumulated state. Dispatches by msg.get_type()."""
        msg_type = msg.get_type()
        if msg_type == "HEARTBEAT":
            self._apply_heartbeat(msg)
        elif msg_type == "GLOBAL_POSITION_INT":
            self._apply_global_position_int(msg)
        elif msg_type == "ATTITUDE":
            self._apply_attitude(msg)
        elif msg_type == "SYS_STATUS":
            self._apply_sys_status(msg)
        elif msg_type == "VFR_HUD":
            self._apply_vfr_hud(msg)
        elif msg_type == "GPS_RAW_INT":
            self._apply_gps_raw_int(msg)
        elif msg_type == "HOME_POSITION":
            self._apply_home_position(msg)
        elif msg_type == "GPS_GLOBAL_ORIGIN":
            self._apply_gps_global_origin(msg)

    def _apply_heartbeat(self, msg: Any) -> None:
        """HEARTBEAT: custom_mode = flight mode number, map to name; base_mode = armed bit."""
        self._heartbeat_count += 1
        self._last_heartbeat_time = time.monotonic()
        self._last_heartbeat_at = datetime.now(timezone.utc)
        custom_mode = getattr(msg, "custom_mode", 0)
        self._accum["mode"] = self._mode_mapping.get(custom_mode, "UNKNOWN")
        base_mode = getattr(msg, "base_mode", 0)
        self._accum["armed"] = bool(base_mode & 128)  # MAV_MODE_FLAG_ARMED

    def set_mode_mapping(self, mapping: dict[int, str]) -> None:
        """Override flight mode mapping (for INAV, generic adapters)."""
        self._mode_mapping = dict(mapping)

    def _apply_global_position_int(self, msg: Any) -> None:
        """GLOBAL_POSITION_INT (id 33): lat/lon degE7, relative_alt mm, hdg cdeg.
        Sentinel: hdg=65535 (UINT16_MAX) means unknown. See mavlink.io/common#GLOBAL_POSITION_INT.
        """
        # lat, lon: degE7 -> degrees
        self._accum["lat"] = msg.lat / 1e7
        self._accum["lon"] = msg.lon / 1e7
        # relative_alt: mm -> m
        self._accum["rel_alt_m"] = msg.relative_alt / 1000.0
        # hdg: centidegrees, UINT16_MAX=65535 means unknown
        hdg = getattr(msg, "hdg", UINT16_MAX)
        if hdg != UINT16_MAX:
            self._accum["heading_deg"] = hdg / 100.0
        # vz: cm/s, positive down; climb = -vz
        vz = getattr(msg, "vz", None)
        if vz is not None:
            self._accum["climb_rate_m_s"] = -vz / 100.0

    def _apply_attitude(self, msg: Any) -> None:
        """ATTITUDE (id 30): roll, pitch, yaw in radians. See mavlink.io/common#ATTITUDE."""
        self._accum["roll_rad"] = getattr(msg, "roll", _nan())
        self._accum["pitch_rad"] = getattr(msg, "pitch", _nan())
        self._accum["yaw_rad"] = getattr(msg, "yaw", _nan())

    def _apply_sys_status(self, msg: Any) -> None:
        """SYS_STATUS (id 1): voltage_battery mV (65535=invalid), current_battery cA (-1=invalid).
        See mavlink.io/common#SYS_STATUS."""
        voltage = getattr(msg, "voltage_battery", UINT16_MAX)
        if voltage != UINT16_MAX:
            self._accum["voltage_v"] = voltage / 1000.0
        current = getattr(msg, "current_battery", SYS_STATUS_CURRENT_INVALID)
        if current != SYS_STATUS_CURRENT_INVALID:
            self._accum["current_a"] = current / 100.0

    def _apply_vfr_hud(self, msg: Any) -> None:
        """VFR_HUD (id 74): heading deg, groundspeed/airspeed m/s. See mavlink.io/common#VFR_HUD."""
        self._accum["heading_deg"] = getattr(msg, "heading", _nan())
        self._accum["groundspeed_m_s"] = getattr(msg, "groundspeed", _nan())
        self._accum["airspeed_m_s"] = getattr(msg, "airspeed", _nan())

    def _apply_gps_raw_int(self, msg: Any) -> None:
        """GPS_RAW_INT (id 24): fix_type, satellites_visible. See mavlink.io/common#GPS_RAW_INT."""
        fix_type = getattr(msg, "fix_type", None)
        if fix_type is not None:
            self._accum["gps_fix_type"] = int(fix_type)
        sat = getattr(msg, "satellites_visible", None)
        if sat is not None and sat != 255:  # 255 = unknown
            self._accum["satellites_visible"] = int(sat)

    def _apply_home_position(self, msg: Any) -> None:
        """HOME_POSITION (id 242): latitude, longitude degE7. See mavlink.io/common#HOME_POSITION."""
        lat = getattr(msg, "latitude", None)
        lon = getattr(msg, "longitude", None)
        if lat is not None and lon is not None:
            self._accum["home_lat"] = lat / 1e7
            self._accum["home_lon"] = lon / 1e7

    def _apply_gps_global_origin(self, msg: Any) -> None:
        """GPS_GLOBAL_ORIGIN (id 49): latitude, longitude degE7 (INAV uses for home).
        Same semantics as HOME_POSITION; both populate home_lat/home_lon. See mavlink.io/common#GPS_GLOBAL_ORIGIN.
        """
        lat = getattr(msg, "latitude", None)
        lon = getattr(msg, "longitude", None)
        if lat is not None and lon is not None:
            self._accum["home_lat"] = lat / 1e7
            self._accum["home_lon"] = lon / 1e7

    def _is_stale(self) -> bool:
        """True if no HEARTBEAT received within timeout."""
        if self._last_heartbeat_time is None:
            return True
        return (time.monotonic() - self._last_heartbeat_time) > self._heartbeat_timeout

    def build_state(
        self,
        telemetry_status_override: TelemetryStatus | None = None,
        reconnect_count: int = 0,
        last_disconnect_reason: str | None = None,
    ) -> AircraftState:
        """Build AircraftState from accumulated values. Sets connected=False if stale."""
        connected = not self._is_stale()
        status = telemetry_status_override or ("connected" if connected else "stale")
        now = time.monotonic()
        heartbeat_age_s = (
            (now - self._last_heartbeat_time)
            if self._last_heartbeat_time is not None
            else float("nan")
        )
        return AircraftState(
            connected=connected,
            heartbeat=self._heartbeat_count,
            last_heartbeat_at=self._last_heartbeat_at,
            heartbeat_age_s=heartbeat_age_s,
            telemetry_status=status,
            reconnect_count=reconnect_count,
            last_disconnect_reason=last_disconnect_reason,
            mode=self._accum["mode"],
            armed=self._accum["armed"],
            lat=self._accum["lat"],
            lon=self._accum["lon"],
            rel_alt_m=self._accum["rel_alt_m"],
            heading_deg=self._accum["heading_deg"],
            roll_rad=self._accum["roll_rad"],
            pitch_rad=self._accum["pitch_rad"],
            yaw_rad=self._accum["yaw_rad"],
            voltage_v=self._accum["voltage_v"],
            current_a=self._accum["current_a"],
            groundspeed_m_s=self._accum["groundspeed_m_s"],
            airspeed_m_s=self._accum["airspeed_m_s"],
            timestamp=datetime.now(timezone.utc),
            climb_rate_m_s=self._accum["climb_rate_m_s"],
            gps_fix_type=self._accum["gps_fix_type"],
            satellites_visible=self._accum["satellites_visible"],
            home_lat=self._accum["home_lat"],
            home_lon=self._accum["home_lon"],
        )
