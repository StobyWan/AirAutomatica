"""Telemetry interface."""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from airautomatica.models.state import AircraftState


class TelemetrySource(ABC):
    """Abstract base for telemetry sources that yield AircraftState updates."""

    @abstractmethod
    async def stream(self) -> AsyncIterator[AircraftState]:
        """Stream telemetry state updates indefinitely."""
        ...
