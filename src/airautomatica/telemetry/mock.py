"""Mock telemetry for local development."""

import asyncio
import math
import time
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from typing import Optional

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.base import TelemetrySource
from airautomatica.telemetry.capabilities import (
    CapabilityInfo,
    ardupilot_profile,
    capability_info,
    generic_readonly_profile,
    inav_profile,
)

# Mode sequence for ArduPilot/INAV mock: cycle through common APM modes
# (from telemetry_contract.md / MODE_MAPPING_APM)
_MOCK_MODE_SEQUENCE = [
    "MANUAL",
    "FBWA",
    "AUTO",
    "GUIDED",
    "RTL",
    "LOITER",
]


def _get_profile_and_firmware(mock_type: str) -> tuple[str, str]:
    """Return (firmware_name, profile_id) for mock_type."""
    if mock_type == "ardupilot":
        return "ArduPilot (Mock)", "ardupilot"
    if mock_type == "inav":
        return "INAV (Mock)", "inav"
    return "Unknown (Mock)", "generic"


def _get_capability_info(mock_type: str) -> CapabilityInfo:
    """Build CapabilityInfo for mock_type."""
    firmware_name, profile_id = _get_profile_and_firmware(mock_type)
    if mock_type == "ardupilot":
        profile = ardupilot_profile()
    elif mock_type == "inav":
        profile = inav_profile()
    else:
        profile = generic_readonly_profile()
    return capability_info(firmware_name, profile_id, profile)


class MockTelemetry(TelemetrySource):
    """Simulates changing flight data for local development.

    Supports mock_type: ardupilot, inav, generic. Each emits matching CapabilityInfo
    and uses doc-based realistic values and mode sequences from MODE_MAPPING_APM.
    Simulates one disconnect after startup so users see what happens when FC is unplugged.
    """

    def __init__(
        self,
        mock_type: str = "ardupilot",
        capability_callback: Optional[Callable[[CapabilityInfo], None]] = None,
        interval_sec: float = 0.5,
        heartbeat_interval_sec: float = 1.0,
    ) -> None:
        self._mock_type = (
            mock_type if mock_type in ("ardupilot", "inav", "generic") else "ardupilot"
        )
        self._capability_callback = capability_callback
        self._interval = interval_sec
        self._heartbeat_interval = heartbeat_interval_sec
        self._heartbeat = 0
        self._last_heartbeat_time: float | None = None
        self._disconnect_demo_done = False
        self._capability_emitted = False

    def _mode_for_heartbeat(self) -> str:
        """Return mode for current heartbeat. Cycles through APM modes."""
        if self._mock_type == "generic":
            return "UNKNOWN"
        idx = (self._heartbeat // 3) % len(_MOCK_MODE_SEQUENCE)
        return _MOCK_MODE_SEQUENCE[idx]

    def _make_connected_state(self, t: float) -> AircraftState:
        """Build a connected state at time t. Doc-based value ranges."""
        now_mono = time.monotonic()
        now = datetime.now(timezone.utc)

        if self._last_heartbeat_time is None or (
            now_mono - self._last_heartbeat_time >= self._heartbeat_interval
        ):
            self._last_heartbeat_time = now_mono
            self._heartbeat += 1

        heartbeat_age_s = (
            now_mono - self._last_heartbeat_time
            if self._last_heartbeat_time is not None
            else 0.0
        )

        # Doc-based ranges: voltage 11-14V, current 0-30A, groundspeed 0-50 m/s
        lat = 37.6213 + 0.0001 * math.sin(t)
        lon = -122.3790 + 0.0001 * math.cos(t)
        rel_alt_m = 50.0 + 10.0 * math.sin(t * 0.5)
        heading_deg = (t * 20) % 360
        roll_rad = 0.1 * math.sin(t)
        pitch_rad = -0.05 * math.cos(t)
        yaw_rad = math.radians(heading_deg)
        voltage_v = 12.4 - 0.01 * (self._heartbeat % 100)  # 11-14V range
        current_a = 2.5 + 0.5 * math.sin(t * 0.3)  # 0-30A typical
        groundspeed_m_s = 15.0 + 5.0 * math.sin(t * 0.2)  # 0-50 m/s
        airspeed_m_s = groundspeed_m_s + 2.0
        climb_rate_m_s = 0.5 * math.sin(t * 0.4)
        mode = self._mode_for_heartbeat()
        home_lat, home_lon = 37.6213, -122.3790
        return AircraftState(
            connected=True,
            heartbeat=self._heartbeat,
            mode=mode,
            armed=False,
            lat=lat,
            lon=lon,
            rel_alt_m=rel_alt_m,
            heading_deg=heading_deg,
            roll_rad=roll_rad,
            pitch_rad=pitch_rad,
            yaw_rad=yaw_rad,
            voltage_v=round(voltage_v, 2),
            current_a=round(current_a, 2),
            groundspeed_m_s=round(groundspeed_m_s, 2),
            airspeed_m_s=round(airspeed_m_s, 2),
            timestamp=now,
            last_heartbeat_at=now,
            heartbeat_age_s=round(heartbeat_age_s, 2),
            telemetry_status="connected",
            reconnect_count=0,
            last_disconnect_reason=None,
            climb_rate_m_s=round(climb_rate_m_s, 2),
            gps_fix_type=3,
            satellites_visible=12,
            home_lat=home_lat,
            home_lon=home_lon,
        )

    async def stream(self) -> AsyncIterator[AircraftState]:
        """Yield simulated state updates at regular intervals."""
        if not self._capability_emitted and self._capability_callback is not None:
            self._capability_emitted = True
            cap = _get_capability_info(self._mock_type)
            self._capability_callback(cap)

        t = 0.0
        while True:
            if not self._disconnect_demo_done and self._heartbeat >= 4:
                self._disconnect_demo_done = True
                now = datetime.now(timezone.utc)
                disconnected = AircraftState(
                    connected=False,
                    heartbeat=self._heartbeat,
                    mode="UNKNOWN",
                    armed=False,
                    lat=37.6213,
                    lon=-122.3790,
                    rel_alt_m=50.0,
                    heading_deg=0.0,
                    roll_rad=0.0,
                    pitch_rad=0.0,
                    yaw_rad=0.0,
                    voltage_v=0.0,
                    current_a=0.0,
                    groundspeed_m_s=0.0,
                    airspeed_m_s=0.0,
                    timestamp=now,
                    last_heartbeat_at=None,
                    heartbeat_age_s=float("nan"),
                    telemetry_status="disconnected",
                    reconnect_count=1,
                    last_disconnect_reason="simulated_disconnect",
                    climb_rate_m_s=0.0,
                )
                yield disconnected
                await asyncio.sleep(1.0)
                backoff = AircraftState(
                    connected=False,
                    heartbeat=self._heartbeat,
                    mode="UNKNOWN",
                    armed=False,
                    lat=37.6213,
                    lon=-122.3790,
                    rel_alt_m=50.0,
                    heading_deg=0.0,
                    roll_rad=0.0,
                    pitch_rad=0.0,
                    yaw_rad=0.0,
                    voltage_v=0.0,
                    current_a=0.0,
                    groundspeed_m_s=0.0,
                    airspeed_m_s=0.0,
                    timestamp=datetime.now(timezone.utc),
                    last_heartbeat_at=None,
                    heartbeat_age_s=float("nan"),
                    telemetry_status="backoff",
                    reconnect_count=1,
                    last_disconnect_reason="simulated_disconnect",
                    climb_rate_m_s=0.0,
                )
                yield backoff
                await asyncio.sleep(0.5)

            t += 0.1
            state = self._make_connected_state(t)
            yield state
            await asyncio.sleep(self._interval)
