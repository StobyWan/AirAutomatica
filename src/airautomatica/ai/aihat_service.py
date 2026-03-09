"""AI HAT service for Raspberry Pi 5 onboard perception.

TODO: Implement when Raspberry Pi 5 + AI HAT+ hardware is available.
- Input: camera frame (rpicam, picamera2). infer(state) has no image yet.
- HailoRT + HEF model from Hailo Model Zoo. See hailo-rpi5-examples on GitHub.
- hailo-all package, HailoRT Python API. Device auto-discovery via PCIe.
"""

from datetime import datetime, timezone

from airautomatica.ai.models import AiResult
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState


class AiHatAiService(AiService):
    """Raspberry Pi AI HAT+ onboard perception. Not LLM reasoning—vision/detection only.

    In flight: Matek/ArduPilot = flight control; AI HAT = perception; mission logic = rules.
    """

    def __init__(self, model_name: str, device: str) -> None:
        """device param is legacy/placeholder; HailoRT uses auto-discovery."""
        self._model_name = model_name
        self._device = device
        # TODO: Load HEF model, initialize HailoRT

    async def infer(self, state: AircraftState | None) -> AiResult:
        """Run inference on AI HAT. TODO: implement hardware path."""
        # TODO: Capture camera frame (rpicam/picamera2)
        # TODO: Run inference via HailoRT
        # TODO: Parse detection output into AiResult (label, confidence, bbox, etc.)
        return AiResult(
            label="aihat_scaffold",
            confidence=0.0,
            summary="AI HAT backend not yet implemented",
            source_backend="aihat",
            timestamp=datetime.now(timezone.utc),
            metadata={
                "model_name": self._model_name,
                "device": self._device,
                "todo": "Implement Hailo/Pi AI Kit inference",
            },
        )
