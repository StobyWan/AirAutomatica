"""AI service interface. One abstraction for mock, ollama, and aihat modes."""

from abc import ABC, abstractmethod
from typing import Optional

from airautomatica.ai.models import AiResult
from airautomatica.models.state import AircraftState


class AiService(ABC):
    """Single AI service abstraction. Mode-based implementations produce normalized AiResult.

    Ollama/Mock: infer(state) uses state only.
    AiHat (future): will receive frames from camera layer; state is context.
    """

    @abstractmethod
    async def infer(self, state: Optional[AircraftState]) -> AiResult:
        """
        Run inference. Receives aircraft state as context.
        Returns normalized AiResult. Non-flight-critical.
        """
        ...
