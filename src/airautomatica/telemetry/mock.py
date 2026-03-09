"""Mock telemetry for local development."""

import asyncio
import math
from datetime import datetime, timezone
from typing import AsyncIterator

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.base import TelemetrySource


class MockTelemetry(TelemetrySource):
    """Simulates changing flight data for local development."""

    def __init__(self, interval_sec: float = 0.5) -> None:
        self._interval = interval_sec
        self._heartbeat = 0

    async def stream(self) -> AsyncIterator[AircraftState]:
        """Yield simulated state updates at regular intervals."""
        t = 0.0
        while True:
            self._heartbeat += 1
            t += 0.1
            # Simulate gentle orbit around a point
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
            mode = "GUIDED" if (self._heartbeat % 20) > 10 else "AUTO"

            now = datetime.now(timezone.utc)
            state = AircraftState(
                connected=True,
                heartbeat=self._heartbeat,
                mode=mode,
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
                heartbeat_age_s=0.0,
                telemetry_status="connected",
                reconnect_count=0,
                last_disconnect_reason=None,
            )
            yield state
            await asyncio.sleep(self._interval)
