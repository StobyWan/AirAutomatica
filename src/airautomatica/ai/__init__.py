"""AI service. One abstraction for mock, lmstudio, and aihat modes."""

from airautomatica.ai.aihat_service import AiHatAiService
from airautomatica.ai.lmstudio_service import LmStudioAiService
from airautomatica.ai.mock_service import MockAiService
from airautomatica.ai.models import AiResult
from airautomatica.ai.service import AiService

__all__ = [
    "AiService",
    "AiResult",
    "MockAiService",
    "LmStudioAiService",
    "AiHatAiService",
]
