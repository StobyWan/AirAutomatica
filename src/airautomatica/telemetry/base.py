"""Telemetry interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from airautomatica.models.state import AircraftState


class TelemetrySource(ABC):
    """Abstract base for telemetry sources that yield AircraftState updates."""

    @abstractmethod
    async def stream(self) -> AsyncIterator[AircraftState]:
        """Stream telemetry state updates indefinitely."""
        if False:
            yield  # makes this an async generator for type checker
        raise NotImplementedError
