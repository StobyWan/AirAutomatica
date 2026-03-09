"""Mock AI service for tests and early development."""

from datetime import datetime, timezone

from airautomatica.ai.models import AiResult
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState


class MockAiService(AiService):
    """Deterministic fake AI results. No network or hardware."""

    def __init__(self, label: str = "mock_ok", confidence: float = 0.99) -> None:
        self._label = label
        self._confidence = confidence
        self._call_count = 0

    async def infer(self, state: AircraftState | None) -> AiResult:
        """Return deterministic result based on state and call count."""
        self._call_count += 1
        mode = state.mode if state else "UNKNOWN"
        summary = f"Mock inference #{self._call_count} (mode={mode})"
        return AiResult(
            label=self._label,
            confidence=self._confidence,
            summary=summary,
            source_backend="mock",
            timestamp=datetime.now(timezone.utc),
            metadata={"call_count": self._call_count, "mode": mode},
        )
