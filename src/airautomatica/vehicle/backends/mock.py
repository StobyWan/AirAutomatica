"""Mock vehicle backend for bench mode. Accepts commands, no hardware output."""

from airautomatica.vehicle.backends.base import VehicleBackendBase
from airautomatica.vehicle.control import RoverControlMessage


class MockVehicleBackend(VehicleBackendBase):
    """Bench mode: accept commands, no hardware output."""

    def __init__(self) -> None:
        self._last_command: RoverControlMessage | None = None

    def send_command(self, msg: RoverControlMessage) -> None:
        self._last_command = msg

    def get_status(self) -> dict:
        return {
            "backend": "mock",
            "connected": True,
            "last_command": (
                self._last_command.to_dict() if self._last_command else None
            ),
        }
