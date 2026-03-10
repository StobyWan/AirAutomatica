"""Composed AI service: local LLM provider + optional AI HAT layer.

AI HAT and local LLM are complementary: local LLM handles inference/text reasoning,
AI HAT handles hardware-accelerated vision. When both are enabled, AI HAT takes
priority when it produces meaningful output; otherwise the local LLM result is used.
"""

import logging
from typing import Optional

from airautomatica.ai.models import AiResult
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)

# AI HAT scaffold returns this label; not a real detection
_AIHAT_SCAFFOLD_LABEL = "aihat_scaffold"


def _is_meaningful_aihat_result(result: AiResult) -> bool:
    """True if AI HAT produced a real detection, not scaffold placeholder."""
    if result.source_backend != "aihat":
        return False
    if result.label == _AIHAT_SCAFFOLD_LABEL:
        return False
    if result.confidence <= 0.0:
        return False
    return True


class ComposedAiService(AiService):
    """Composes a base local LLM provider with an optional AI HAT layer.

    - base_ai_service: MockAiService or OllamaAiService
    - aihat_service: optional AiHatAiService; when set and producing meaningful
      output, its result is used; else the base provider's result is used.
    """

    def __init__(
        self,
        base_ai_service: AiService,
        aihat_service: Optional[AiService] = None,
    ) -> None:
        self._base = base_ai_service
        self._aihat = aihat_service

    async def infer(self, state: AircraftState | None) -> AiResult:
        """Run inference. Tries AI HAT first when enabled; falls back to base."""
        if self._aihat is not None:
            try:
                hat_result = await self._aihat.infer(state)
                if _is_meaningful_aihat_result(hat_result):
                    return hat_result
            except Exception as e:
                logger.debug("AI HAT inference failed, using base: %s", e)
        return await self._base.infer(state)
