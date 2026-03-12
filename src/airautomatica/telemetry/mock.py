"""Mock telemetry for local development."""

import asyncio
import math
import time
from datetime import datetime, timezone
from typing import AsyncIterator

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.base import TelemetrySource


class MockTelemetry(TelemetrySource):
    """Simulates changing flight data for local development.
    Simulates one disconnect after startup so users see what happens when FC is unplugged.
    Simulates heartbeat at ~1 Hz so heartbeat_age_s increases between heartbeats.
    """

    def __init__(
        self, interval_sec: float = 0.5, heartbeat_interval_sec: float = 1.0
    ) -> None:
        self._interval = interval_sec
        self._heartbeat_interval = heartbeat_interval_sec
        self._heartbeat = 0
        self._last_heartbeat_time: float | None = None
        self._disconnect_demo_done = False

    def _make_connected_state(self, t: float) -> AircraftState:
        """Build a connected state at time t. Simulates heartbeat at intervals."""
        now_mono = time.monotonic()
        now = datetime.now(timezone.utc)

        # Simulate heartbeat: only "receive" one every heartbeat_interval_sec
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

        lat = 37.6213 + 0.0001 * math.sin(t)
        lon = -122.3790 + 0.0001 * math.cos(t)
        rel_alt_m = 50.0 + 10.0 * math.sin(t * 0.5)
        heading_deg = (t * 20) % 360
        roll_rad = 0.1 * math.sin(t)
        pitch_rad = -0.05 * math.cos(t)
        yaw_rad = math.radians(heading_deg)
        voltage_v = 12.4 - 0.01 * (self._heartbeat % 100)
        current_a = 2.5 + 0.5 * math.sin(t * 0.3)
        groundspeed_m_s = 15.0 + 5.0 * math.sin(t * 0.2)
        airspeed_m_s = groundspeed_m_s + 2.0
        climb_rate_m_s = 0.5 * math.sin(t * 0.4)
        mode = "GUIDED" if (self._heartbeat % 20) > 10 else "AUTO"
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
