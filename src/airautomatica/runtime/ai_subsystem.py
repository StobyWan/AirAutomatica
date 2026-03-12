"""Runtime holder for AI subsystem. Supports hot-reload when settings change."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airautomatica.ai.ollama_task_service import OllamaTaskService
    from airautomatica.ai.service import AiService

logger = logging.getLogger(__name__)


@dataclass
class ReloadResult:
    """Result of AI subsystem reload."""

    success: bool
    error: Optional[str] = None
    provider_before: Optional[str] = None
    provider_after: Optional[str] = None


class AiSubsystemHolder:
    """Holds active ai_service and task_service. Supports atomic swap on reload."""

    def __init__(
        self,
        ai_service: "AiService",
        task_service: "OllamaTaskService",
    ) -> None:
        self._ai_service = ai_service
        self._task_service = task_service

    def get_ai_service(self) -> "AiService":
        return self._ai_service

    def get_task_service(self) -> "OllamaTaskService":
        return self._task_service

    def swap(
        self,
        ai_service: "AiService",
        task_service: "OllamaTaskService",
    ) -> None:
        """Atomically replace services. Call only after new services are created successfully."""
        self._ai_service = ai_service
        self._task_service = task_service
