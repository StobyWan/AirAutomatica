"""MAVLink vehicle backend. Sends rover commands via MANUAL_CONTROL or RC_CHANNELS_OVERRIDE."""

from typing import Any

from airautomatica.vehicle.backends.base import VehicleBackendBase
from airautomatica.vehicle.control import RoverControlMessage


class MavlinkVehicleBackend(VehicleBackendBase):
    """Send rover commands via MAVLink. Requires connection to flight controller."""

    def __init__(self) -> None:
        self._connected = False
        self._last_command: RoverControlMessage | None = None

    def send_command(self, msg: RoverControlMessage) -> None:
        self._last_command = msg
        if not self._connected:
            return
        # TODO: Send MANUAL_CONTROL or RC_CHANNELS_OVERRIDE via pymavlink
        # steering -> channel 0, throttle -> channel 2, etc.

    def get_status(self) -> dict[str, Any]:
        return {
            "backend": "mavlink",
            "connected": self._connected,
            "last_command": (
                self._last_command.to_dict() if self._last_command else None
            ),
        }
