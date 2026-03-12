"""Task orchestration for Ollama. Provider-aware: ollama or mock."""

import logging
from datetime import datetime, timezone
from typing import Any, Protocol, Union

from airautomatica.ai.json_utils import extract_json
from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_service import OllamaAiService
from airautomatica.ai.ollama_tasks import (
    DebriefSummaryResult,
    EventClassificationResult,
    OllamaTaskType,
    TelemetrySummaryResult,
    build_prompt,
    get_format_for_task,
    parse_debrief_summary_response,
    parse_event_classification_response,
    parse_perception_response,
    parse_telemetry_summary_response,
)

logger = logging.getLogger(__name__)

OllamaTaskResult = Union[
    AiResult,
    TelemetrySummaryResult,
    EventClassificationResult,
    DebriefSummaryResult,
]


class _GenerateRawProtocol(Protocol):
    """Protocol for objects that provide generate_raw (OllamaAiService or ScheduledOllamaExecutor)."""

    async def generate_raw(
        self, prompt: str, *, format: str | dict[str, Any] | None = None
    ) -> str: ...


class OllamaTaskService:
    """Orchestrates task-based Ollama inference. Mock returns stubs; ollama calls API."""

    def __init__(
        self,
        provider: str,
        ollama_service: OllamaAiService | _GenerateRawProtocol | None = None,
    ) -> None:
        self._provider = provider
        self._ollama = ollama_service
        if provider == "ollama" and ollama_service is None:
            raise ValueError("ollama_service required when provider is ollama")

    @property
    def provider(self) -> str:
        """Provider used for inference: 'mock' or 'ollama'."""
        return self._provider

    async def infer_task(
        self,
        task_type: OllamaTaskType,
        context: dict[str, Any],
    ) -> OllamaTaskResult:
        """Run task. Returns typed result; never crashes on malformed Ollama output."""
        if self._provider == "mock":
            return _mock_result(task_type)
        # provider is ollama; _ollama is guaranteed non-None by __init__
        assert self._ollama is not None
        prompt = build_prompt(task_type, context)
        fmt = get_format_for_task(task_type)
        try:
            content = await self._ollama.generate_raw(prompt, format=fmt)
        except Exception as e:
            logger.warning("Ollama generate_raw failed: %s", e)
            return _fallback_result(task_type, str(e))
        raw_preview = (content or "").strip()
        logger.debug(
            "Ollama raw response task=%s len=%d: %s%s",
            task_type.value,
            len(raw_preview),
            raw_preview[:200],
            "..." if len(raw_preview) > 200 else "",
        )
        raw = extract_json(content)
        if raw is None:
            logger.warning(
                "Ollama JSON extraction failed task=%s len=%d: %s%s",
                task_type.value,
                len(raw_preview),
                raw_preview[:300],
                "..." if len(raw_preview) > 300 else "",
            )
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
    if task_type == OllamaTaskType.DEBRIEF_SUMMARY:
        return DebriefSummaryResult(
            summary="Mock post-flight summary. Session completed normally.",
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
    if task_type == OllamaTaskType.DEBRIEF_SUMMARY:
        return DebriefSummaryResult(
            summary=f"Debrief summary unavailable: {reason[:150]}",
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
    if task_type == OllamaTaskType.DEBRIEF_SUMMARY:
        return parse_debrief_summary_response(raw)
    return parse_telemetry_summary_response(raw)
