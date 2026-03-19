"""Abstract base for vehicle control backends."""

from abc import ABC, abstractmethod
from typing import Any

from airautomatica.vehicle.control import RoverControlMessage


class VehicleBackendBase(ABC):
    """Abstract interface for sending vehicle commands to FC or Arduino."""

    @abstractmethod
    def send_command(self, msg: RoverControlMessage) -> None:
        """Send normalized control to hardware. No-op for mock."""
        ...

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Return backend status (connected, last_command, etc.)."""
        ...
