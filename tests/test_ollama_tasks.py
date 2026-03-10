"""Tests for Ollama task types, prompt builders, parsers, and task service."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_service import OllamaAiService
from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.ai.ollama_tasks import (
    EventClassificationResult,
    OllamaTaskType,
    TelemetrySummaryResult,
    build_prompt,
    parse_event_classification_response,
    parse_perception_response,
    parse_telemetry_summary_response,
)
from airautomatica.models.state import AircraftState

# --- Prompt builders ---


def test_build_prompt_perception_empty_context() -> None:
    """Perception prompt with no state produces non-empty prompt with schema."""
    prompt = build_prompt(OllamaTaskType.PERCEPTION_DETECTION, {})
    assert len(prompt) > 0
    assert "JSON" in prompt
    assert "label" in prompt
    assert "confidence" in prompt
    assert "mode=unknown" in prompt


def test_build_prompt_perception_with_state() -> None:
    """Perception prompt with state includes aircraft context."""
    state = AircraftState(
        connected=True,
        heartbeat=1,
        mode="AUTO",
        lat=37.0,
        lon=-122.0,
        rel_alt_m=100.0,
        heading_deg=90.0,
        roll_rad=0.0,
        pitch_rad=0.0,
        yaw_rad=0.0,
        voltage_v=12.5,
        current_a=2.0,
        groundspeed_m_s=10.0,
        airspeed_m_s=12.0,
        timestamp=datetime.now(timezone.utc),
    )
    prompt = build_prompt(OllamaTaskType.PERCEPTION_DETECTION, {"state": state})
    assert "AUTO" in prompt
    assert "100" in prompt
    assert "12.5" in prompt


def test_build_prompt_telemetry_summary() -> None:
    """Telemetry summary prompt is schema-first and non-empty."""
    prompt = build_prompt(OllamaTaskType.TELEMETRY_SUMMARY, {})
    assert len(prompt) > 0
    assert "status" in prompt
    assert "summary" in prompt
    assert "concerns" in prompt
    assert "recommendations" in prompt


def test_build_prompt_event_classification() -> None:
    """Event classification prompt is schema-first and non-empty."""
    prompt = build_prompt(OllamaTaskType.EVENT_CLASSIFICATION, {})
    assert len(prompt) > 0
    assert "severity" in prompt
    assert "category" in prompt
    assert "likely_causes" in prompt
    assert "recommended_checks" in prompt


# --- Perception parser ---


def test_parse_perception_valid() -> None:
    """Valid perception dict produces AiResult matching AiResult.from_dict behavior."""
    raw = {
        "label": "person",
        "confidence": 0.9,
        "summary": "Person detected",
        "bbox": [10, 20, 50, 60],
        "action": "hold",
    }
    result = parse_perception_response(raw, "ollama")
    assert isinstance(result, AiResult)
    assert result.label == "person"
    assert result.confidence == 0.9
    assert result.summary == "Person detected"
    assert result.bbox == (10.0, 20.0, 50.0, 60.0)
    assert result.action == "hold"
    assert result.source_backend == "ollama"


def test_parse_perception_partial() -> None:
    """Partial perception dict gets defaults from AiResult.from_dict."""
    raw = {"label": "vehicle"}
    result = parse_perception_response(raw, "ollama")
    assert result.label == "vehicle"
    assert result.confidence == 0.0
    assert result.summary == ""


def test_parse_perception_none() -> None:
    """None input produces safe AiResult."""
    result = parse_perception_response(None, "ollama")
    assert isinstance(result, AiResult)
    assert result.label == "unknown"


def test_parse_perception_not_dict() -> None:
    """Non-dict input produces safe AiResult."""
    result = parse_perception_response("not a dict", "ollama")  # type: ignore[arg-type]
    assert isinstance(result, AiResult)


# --- Telemetry summary parser ---


def test_parse_telemetry_summary_valid() -> None:
    """Valid telemetry summary parses correctly."""
    raw = {
        "status": "ok",
        "summary": "Aircraft in AUTO, battery nominal",
        "concerns": ["altitude drift"],
        "recommendations": ["monitor altitude"],
    }
    result = parse_telemetry_summary_response(raw)
    assert isinstance(result, TelemetrySummaryResult)
    assert result.status == "ok"
    assert result.summary == "Aircraft in AUTO, battery nominal"
    assert result.concerns == ("altitude drift",)
    assert result.recommendations == ("monitor altitude",)


def test_parse_telemetry_summary_empty_arrays() -> None:
    """Empty arrays become empty tuples."""
    raw = {"status": "ok", "summary": "All good", "concerns": [], "recommendations": []}
    result = parse_telemetry_summary_response(raw)
    assert result.concerns == ()
    assert result.recommendations == ()


def test_parse_telemetry_summary_missing_fields() -> None:
    """Missing fields get safe defaults."""
    raw: dict[str, Any] = {}
    result = parse_telemetry_summary_response(raw)
    assert result.status == "unknown"
    assert result.summary == ""
    assert result.concerns == ()
    assert result.recommendations == ()


def test_parse_telemetry_summary_none() -> None:
    """None input degrades safely."""
    result = parse_telemetry_summary_response(None)
    assert result.status == "unknown"


def test_parse_telemetry_summary_malformed_types() -> None:
    """Malformed types coerce safely: string->single-item, non-list->empty."""
    raw: dict[str, Any] = {
        "status": 123,
        "concerns": "not a list",
        "recommendations": [1, 2, 3],
    }
    result = parse_telemetry_summary_response(raw)
    assert isinstance(result.status, str)
    assert result.concerns == ("not a list",)  # string -> single-item array
    assert result.recommendations == ("1", "2", "3")  # coerced to str


def test_parse_telemetry_summary_null_concerns() -> None:
    """null for list field normalizes to empty tuple."""
    raw: dict[str, Any] = {"status": "ok", "summary": "x", "concerns": None}
    result = parse_telemetry_summary_response(raw)
    assert result.concerns == ()


def test_parse_telemetry_summary_string_recommendations() -> None:
    """String for list field normalizes to single-item tuple."""
    raw: dict[str, Any] = {"status": "ok", "recommendations": "check battery"}
    result = parse_telemetry_summary_response(raw)
    assert result.recommendations == ("check battery",)


def test_parse_telemetry_summary_whitespace_string() -> None:
    """Whitespace-only string for list field normalizes to empty tuple."""
    raw: dict[str, Any] = {"status": "ok", "concerns": "   "}
    result = parse_telemetry_summary_response(raw)
    assert result.concerns == ()


def test_parse_telemetry_summary_malformed_non_list() -> None:
    """Non-list non-string (e.g. int) for list field degrades to empty tuple."""
    raw: dict[str, Any] = {"status": "ok", "concerns": 123}
    result = parse_telemetry_summary_response(raw)
    assert result.concerns == ()


# --- Event classification parser ---


def test_parse_event_classification_valid() -> None:
    """Valid event classification parses correctly."""
    raw = {
        "severity": "warning",
        "category": "telemetry",
        "summary": "Connection stale",
        "likely_causes": ["heartbeat timeout"],
        "recommended_checks": ["check serial link"],
    }
    result = parse_event_classification_response(raw)
    assert isinstance(result, EventClassificationResult)
    assert result.severity == "warning"
    assert result.category == "telemetry"
    assert result.summary == "Connection stale"
    assert result.likely_causes == ("heartbeat timeout",)
    assert result.recommended_checks == ("check serial link",)


def test_parse_event_classification_missing_fields() -> None:
    """Missing fields get defaults."""
    raw: dict[str, Any] = {}
    result = parse_event_classification_response(raw)
    assert result.severity == "info"
    assert result.category == "general"
    assert result.summary == ""
    assert result.likely_causes == ()
    assert result.recommended_checks == ()


def test_parse_event_classification_none() -> None:
    """None input degrades safely."""
    result = parse_event_classification_response(None)
    assert result.severity == "info"


def test_parse_event_classification_invalid_severity() -> None:
    """Invalid severity falls back to info."""
    raw = {"severity": "supercritical", "category": "x"}
    result = parse_event_classification_response(raw)
    assert result.severity == "info"


def test_parse_event_classification_valid_severities() -> None:
    """Valid severity values pass through."""
    for sev in ("info", "warning", "error", "critical"):
        raw = {"severity": sev}
        result = parse_event_classification_response(raw)
        assert result.severity == sev


def test_parse_event_classification_null_likely_causes() -> None:
    """null for list field normalizes to empty tuple."""
    raw: dict[str, Any] = {"severity": "info", "likely_causes": None}
    result = parse_event_classification_response(raw)
    assert result.likely_causes == ()


def test_parse_event_classification_string_recommended_checks() -> None:
    """String for list field normalizes to single-item tuple."""
    raw: dict[str, Any] = {"severity": "info", "recommended_checks": "inspect link"}
    result = parse_event_classification_response(raw)
    assert result.recommended_checks == ("inspect link",)


def test_parse_event_classification_malformed_list() -> None:
    """Non-list non-string for list field degrades to empty tuple."""
    raw: dict[str, Any] = {"severity": "info", "likely_causes": 123}
    result = parse_event_classification_response(raw)
    assert result.likely_causes == ()


# --- Mock-path: OllamaTaskService with provider=mock ---


@pytest.mark.asyncio
async def test_task_service_mock_telemetry_summary() -> None:
    """Mock provider returns valid TelemetrySummaryResult without Ollama."""
    svc = OllamaTaskService(provider="mock")
    result = await svc.infer_task(OllamaTaskType.TELEMETRY_SUMMARY, {})
    assert isinstance(result, TelemetrySummaryResult)
    assert result.status == "ok"
    assert result.summary == "Mock telemetry summary"
    assert result.concerns == ()
    assert result.recommendations == ()


@pytest.mark.asyncio
async def test_task_service_mock_event_classification() -> None:
    """Mock provider returns valid EventClassificationResult without Ollama."""
    svc = OllamaTaskService(provider="mock")
    result = await svc.infer_task(OllamaTaskType.EVENT_CLASSIFICATION, {})
    assert isinstance(result, EventClassificationResult)
    assert result.severity == "info"
    assert result.category == "general"
    assert result.summary == "No significant events"
    assert result.likely_causes == ()
    assert result.recommended_checks == ()


@pytest.mark.asyncio
async def test_task_service_mock_perception() -> None:
    """Mock provider returns AiResult for perception_detection."""
    svc = OllamaTaskService(provider="mock")
    result = await svc.infer_task(OllamaTaskType.PERCEPTION_DETECTION, {})
    assert isinstance(result, AiResult)
    assert result.label == "mock_ok"
    assert result.source_backend == "mock"


# --- Ollama-path: task service with mocked generate_raw ---


@pytest.mark.asyncio
async def test_task_service_ollama_telemetry_summary() -> None:
    """Ollama path parses valid JSON into TelemetrySummaryResult."""
    ollama = OllamaAiService(
        base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
    )
    with patch.object(ollama, "generate_raw", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = '{"status":"ok","summary":"Battery nominal","concerns":[],"recommendations":[]}'
        svc = OllamaTaskService(provider="ollama", ollama_service=ollama)
        result = await svc.infer_task(OllamaTaskType.TELEMETRY_SUMMARY, {})
    assert isinstance(result, TelemetrySummaryResult)
    assert result.status == "ok"
    assert result.summary == "Battery nominal"


@pytest.mark.asyncio
async def test_task_service_ollama_event_classification() -> None:
    """Ollama path parses valid JSON into EventClassificationResult."""
    ollama = OllamaAiService(
        base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
    )
    with patch.object(ollama, "generate_raw", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (
            '{"severity":"warning","category":"telemetry","summary":"Stale heartbeat",'
            '"likely_causes":["timeout"],"recommended_checks":["check link"]}'
        )
        svc = OllamaTaskService(provider="ollama", ollama_service=ollama)
        result = await svc.infer_task(OllamaTaskType.EVENT_CLASSIFICATION, {})
    assert isinstance(result, EventClassificationResult)
    assert result.severity == "warning"
    assert result.summary == "Stale heartbeat"


@pytest.mark.asyncio
async def test_task_service_ollama_malformed_degrades_safely() -> None:
    """Malformed Ollama output returns valid struct, never crashes."""
    ollama = OllamaAiService(
        base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
    )
    with patch.object(ollama, "generate_raw", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "not valid json at all"
        svc = OllamaTaskService(provider="ollama", ollama_service=ollama)
        result = await svc.infer_task(OllamaTaskType.TELEMETRY_SUMMARY, {})
    assert isinstance(result, TelemetrySummaryResult)
    assert result.status == "unknown"
    assert result.summary == ""


@pytest.mark.asyncio
async def test_task_service_ollama_exception_returns_fallback() -> None:
    """When generate_raw raises, task service returns fallback, does not crash."""
    ollama = OllamaAiService(
        base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
    )
    with patch.object(ollama, "generate_raw", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = ConnectionError("Connection refused")
        svc = OllamaTaskService(provider="ollama", ollama_service=ollama)
        result = await svc.infer_task(OllamaTaskType.EVENT_CLASSIFICATION, {})
    assert isinstance(result, EventClassificationResult)
    assert result.severity == "warning"
    assert "Connection refused" in result.summary
