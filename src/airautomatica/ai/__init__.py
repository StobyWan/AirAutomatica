"""AI service. One abstraction for mock, ollama, and aihat modes.

ComposedAiService composes a base provider (mock/ollama) with optional AI HAT layer.
"""

from airautomatica.ai.aihat_service import AiHatAiService
from airautomatica.ai.composed_service import ComposedAiService
from airautomatica.ai.mock_service import MockAiService
from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_service import OllamaAiService
from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.ai.ollama_tasks import (
    DebriefSummaryResult,
    EventClassificationResult,
    OllamaTaskType,
    TelemetrySummaryResult,
)
from airautomatica.ai.service import AiService

__all__ = [
    "AiService",
    "AiResult",
    "ComposedAiService",
    "DebriefSummaryResult",
    "EventClassificationResult",
    "MockAiService",
    "OllamaAiService",
    "OllamaTaskService",
    "OllamaTaskType",
    "TelemetrySummaryResult",
    "AiHatAiService",
]
