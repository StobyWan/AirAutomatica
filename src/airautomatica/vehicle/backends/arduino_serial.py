"""Arduino serial vehicle backend. Sends commands over serial to motor controller."""

from typing import Any

from airautomatica.vehicle.backends.base import VehicleBackendBase
from airautomatica.vehicle.control import RoverControlMessage


class ArduinoSerialVehicleBackend(VehicleBackendBase):
    """Send rover commands over serial to Arduino motor controller."""

    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = 115200) -> None:
        self._port = port
        self._baud = baud
        self._connected = False
        self._last_command: RoverControlMessage | None = None

    def send_command(self, msg: RoverControlMessage) -> None:
        self._last_command = msg
        if not self._connected:
            return
        # TODO: Open serial, send protocol (e.g. "S,0.5,T,0.3\n"), close or keep open

    def get_status(self) -> dict[str, Any]:
        return {
            "backend": "arduino_serial",
            "connected": self._connected,
            "port": self._port,
            "baud": self._baud,
            "last_command": (
                self._last_command.to_dict() if self._last_command else None
            ),
        }
