"""MAVLink telemetry source using VehicleConnectionManager and adapters."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Optional

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.base import TelemetrySource
from airautomatica.telemetry.capabilities import CapabilityInfo
from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer
from airautomatica.telemetry.services.vehicle_connection_manager import (
    VehicleConnectionManager,
)
from airautomatica.telemetry.transport import SerialTransport

logger = logging.getLogger(__name__)

INITIAL_BACKOFF_SEC = 1.0
MAX_BACKOFF_SEC = 60.0
BACKOFF_YIELD_INTERVAL_SEC = 0.5
NO_HEARTBEAT_BACKOFF_SEC = 1.0


class MavlinkTelemetrySource(TelemetrySource):
    """MAVLink telemetry via transport and adapter abstraction.

    Connects SerialTransport, runs VehicleConnectionManager with adapter
    selection, yields AircraftState. Auto-reconnects with backoff.
    """

    def __init__(
        self,
        port: str,
        baud: int,
        heartbeat_timeout_sec: float = 3.0,
        initial_backoff_sec: float = INITIAL_BACKOFF_SEC,
        max_backoff_sec: float = MAX_BACKOFF_SEC,
        capability_callback: Optional[Callable[[CapabilityInfo], None]] = None,
    ) -> None:
        self._port = port
        self._baud = baud
        self._heartbeat_timeout = heartbeat_timeout_sec
        self._initial_backoff = initial_backoff_sec
        self._max_backoff = max_backoff_sec
        self._capability_callback = capability_callback

    async def stream(self) -> AsyncIterator[AircraftState]:
        """Stream state from MAVLink. Auto-reconnects on disconnect."""
        normalizer = MavlinkNormalizer(heartbeat_timeout_sec=self._heartbeat_timeout)
        backoff = self._initial_backoff
        reconnect_count = 0
        last_disconnect_reason: str | None = None

        yield normalizer.build_state(
            telemetry_status_override="starting",
            reconnect_count=reconnect_count,
            last_disconnect_reason=last_disconnect_reason,
        )

        while True:
            transport = SerialTransport(self._port, self._baud)
            manager = VehicleConnectionManager(
                transport,
                heartbeat_timeout_sec=self._heartbeat_timeout,
            )

            try:
                yield normalizer.build_state(
                    telemetry_status_override="connecting",
                    reconnect_count=reconnect_count,
                    last_disconnect_reason=last_disconnect_reason,
                )

                async for state, cap_info in manager.run_connection_cycle(
                    reconnect_count=reconnect_count,
                    last_disconnect_reason=last_disconnect_reason,
                ):
                    if cap_info is not None and self._capability_callback:
                        self._capability_callback(cap_info)
                    yield state

            except RuntimeError as e:
                last_disconnect_reason = str(e)
                logger.warning("Connection cycle failed: %s", e)
            except Exception as e:
                last_disconnect_reason = str(e)
                logger.exception("Connection failed: %s", e)

            reconnect_count += 1

            yield normalizer.build_state(
                telemetry_status_override="disconnected",
                reconnect_count=reconnect_count,
                last_disconnect_reason=last_disconnect_reason,
            )

            logger.info(
                "Reconnecting in %.1fs (attempt %d)...",
                backoff,
                reconnect_count,
            )
            elapsed = 0.0
            while elapsed < backoff:
                await asyncio.sleep(min(BACKOFF_YIELD_INTERVAL_SEC, backoff - elapsed))
                elapsed += BACKOFF_YIELD_INTERVAL_SEC
                yield normalizer.build_state(
                    telemetry_status_override="backoff",
                    reconnect_count=reconnect_count,
                    last_disconnect_reason=last_disconnect_reason,
                )

            backoff = min(backoff * 2, self._max_backoff)
