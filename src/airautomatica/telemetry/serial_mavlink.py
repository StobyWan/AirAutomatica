"""Serial MAVLink telemetry source with robust connection lifecycle.

Delegates to MavlinkTelemetrySource for capability-driven adapter architecture.
Preserved for backward compatibility.
"""

from typing import Callable, Optional

from airautomatica.telemetry.base import TelemetrySource
from airautomatica.telemetry.capabilities import CapabilityInfo
from airautomatica.telemetry.mavlink_telemetry import MavlinkTelemetrySource


class SerialMavlinkTelemetry(TelemetrySource):
    """Read MAVLink telemetry from serial/USB connection to flight controller.

    Uses MavlinkTelemetrySource with transport/adapter abstraction.
    Tracks telemetry_status (starting, connecting, connected, stale,
    disconnected, backoff), auto-reconnects with backoff.
    """

    def __init__(
        self,
        port: str,
        baud: int,
        heartbeat_timeout_sec: float = 3.0,
        initial_backoff_sec: float = 1.0,
        max_backoff_sec: float = 60.0,
        capability_callback: Optional[Callable[[CapabilityInfo], None]] = None,
    ) -> None:
        self._source = MavlinkTelemetrySource(
            port=port,
            baud=baud,
            heartbeat_timeout_sec=heartbeat_timeout_sec,
            initial_backoff_sec=initial_backoff_sec,
            max_backoff_sec=max_backoff_sec,
            capability_callback=capability_callback,
        )

    async def stream(self):
        """Stream state from MAVLink messages. Auto-reconnects on disconnect."""
        async for state in self._source.stream():
            yield state
