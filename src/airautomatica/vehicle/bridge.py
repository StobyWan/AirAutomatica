"""Vehicle control bridge: reads from control store, forwards to backend."""

import asyncio
import logging
from typing import Optional

from airautomatica.config import get_vehicle_mode
from airautomatica.vehicle.backends.base import VehicleBackendBase
from airautomatica.vehicle.backends.mock import MockVehicleBackend
from airautomatica.vehicle.control_store import get_last_control

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 0.05


def _create_backend() -> VehicleBackendBase:
    """Create backend based on mode and config."""
    mode = get_vehicle_mode()
    if mode == "bench":
        return MockVehicleBackend()
    if mode == "rover":
        return MockVehicleBackend()
    return MockVehicleBackend()


async def run_bridge(backend: Optional[VehicleBackendBase] = None) -> None:
    """Poll control store and forward to backend. Runs until cancelled.
    Advisory failsafe: when stale, stop forwarding. Control layer enforces neutral."""
    from airautomatica.vehicle.failsafe import is_stale

    if backend is None:
        backend = _create_backend()
    last_seq = -1
    while True:
        try:
            if is_stale():
                pass
            else:
                msg = get_last_control()
                if msg is not None and msg.seq != last_seq:
                    backend.send_command(msg)
                    last_seq = msg.seq
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Bridge error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SEC)
