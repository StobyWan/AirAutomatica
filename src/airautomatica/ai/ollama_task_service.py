"""Task orchestration for Ollama. Provider-aware: ollama or mock."""

import logging
from datetime import datetime, timezone
from typing import Any, Union

from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_service import OllamaAiService
from airautomatica.ai.ollama_tasks import (
    EventClassificationResult,
    OllamaTaskType,
    TelemetrySummaryResult,
    build_prompt,
    extract_json,
    parse_event_classification_response,
    parse_perception_response,
    parse_telemetry_summary_response,
)

logger = logging.getLogger(__name__)

OllamaTaskResult = Union[AiResult, TelemetrySummaryResult, EventClassificationResult]


class OllamaTaskService:
    """Orchestrates task-based Ollama inference. Mock returns stubs; ollama calls API."""

    def __init__(
        self,
        provider: str,
        ollama_service: OllamaAiService | None = None,
    ) -> None:
        self._provider = provider
        self._ollama = ollama_service
        if provider == "ollama" and ollama_service is None:
            raise ValueError("ollama_service required when provider is ollama")

    async def infer_task(
        self,
        task_type: OllamaTaskType,
        context: dict[str, Any],
    ) -> OllamaTaskResult:
        """Run task. Returns typed result; never crashes on malformed Ollama output."""
        if self._provider == "mock":
            return _mock_result(task_type)
        # provider is ollama
        prompt = build_prompt(task_type, context)
        try:
            content = await self._ollama.generate_raw(prompt)
        except Exception as e:
            logger.warning("Ollama generate_raw failed: %s", e)
            return _fallback_result(task_type, str(e))
        raw = extract_json(content)
        return _parse_task_result(task_type, raw)


def _mock_result(task_type: OllamaTaskType) -> OllamaTaskResult:
    """Deterministic stub for mock provider."""
    if task_type == OllamaTaskType.PERCEPTION_DETECTION:
        return AiResult(
            label="mock_ok",
            confidence=0.99,
            summary="Mock perception (task service)",
            source_backend="mock",
            timestamp=datetime.now(timezone.utc),
        )
    if task_type == OllamaTaskType.TELEMETRY_SUMMARY:
        return TelemetrySummaryResult(
            status="ok",
            summary="Mock telemetry summary",
            concerns=(),
            recommendations=(),
        )
    if task_type == OllamaTaskType.EVENT_CLASSIFICATION:
        return EventClassificationResult(
            severity="info",
            category="general",
            summary="No significant events",
            likely_causes=(),
            recommended_checks=(),
        )
    return TelemetrySummaryResult(
        status="unknown", summary="", concerns=(), recommendations=()
    )


def _fallback_result(task_type: OllamaTaskType, reason: str) -> OllamaTaskResult:
    """Safe fallback when Ollama fails."""
    if task_type == OllamaTaskType.PERCEPTION_DETECTION:
        return AiResult(
            label="error",
            confidence=0.0,
            summary=reason[:200],
            source_backend="ollama",
            timestamp=datetime.now(timezone.utc),
        )
    if task_type == OllamaTaskType.TELEMETRY_SUMMARY:
        return TelemetrySummaryResult(
            status="error",
            summary=reason[:200],
            concerns=(),
            recommendations=(),
        )
    if task_type == OllamaTaskType.EVENT_CLASSIFICATION:
        return EventClassificationResult(
            severity="warning",
            category="error",
            summary=reason[:200],
            likely_causes=(),
            recommended_checks=(),
        )
    return TelemetrySummaryResult(
        status="error", summary=reason[:200], concerns=(), recommendations=()
    )


def _parse_task_result(
    task_type: OllamaTaskType, raw: dict[str, Any] | None
) -> OllamaTaskResult:
    """Parse raw dict with task-specific parser. Never trusts input."""
    if task_type == OllamaTaskType.PERCEPTION_DETECTION:
        return parse_perception_response(raw, "ollama")
    if task_type == OllamaTaskType.TELEMETRY_SUMMARY:
        return parse_telemetry_summary_response(raw)
    if task_type == OllamaTaskType.EVENT_CLASSIFICATION:
        return parse_event_classification_response(raw)
    return parse_telemetry_summary_response(raw)
