"""Tests for Ollama task types, prompt builders, parsers, and task service."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_service import OllamaAiService
from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.ai.ollama_tasks import (
    SCHEMA_EVENT_OBJ,
    SCHEMA_TELEMETRY_OBJ,
    EventClassificationResult,
    OllamaTaskType,
    TelemetrySummaryResult,
    build_prompt,
    get_format_for_task,
    get_telemetry_summary_counts,
    parse_event_classification_response,
    parse_perception_response,
    parse_telemetry_summary_response,
)
from airautomatica.models.state import AircraftState

# --- Prompt builders ---


def test_build_prompt_perception_empty_context() -> None:
    """Perception prompt is compact, no telemetry context."""
    prompt = build_prompt(OllamaTaskType.PERCEPTION_DETECTION, {})
    assert len(prompt) > 0
    assert "JSON" in prompt
    assert "label" in prompt
    assert "confidence" in prompt
    assert "Perception classifier" in prompt
    assert "vehicle" in prompt
    assert "none" in prompt
    assert "mode=" not in prompt
    assert "Context:" not in prompt


def test_build_prompt_perception_ignores_state() -> None:
    """Perception prompt does not include aircraft context (avoids label parroting)."""
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
    assert "AUTO" not in prompt
    assert "100" not in prompt
    assert "12.5" not in prompt


def test_build_prompt_telemetry_summary() -> None:
    """Telemetry summary prompt has analyst framing and schema."""
    prompt = build_prompt(OllamaTaskType.TELEMETRY_SUMMARY, {})
    assert len(prompt) > 0
    assert "JSON" in prompt
    assert "Context" in prompt
    assert "Telemetry analyst" in prompt
    assert "meaningful" in prompt
    assert "Telemetry nominal" in prompt


def test_build_prompt_event_classification() -> None:
    """Event classification prompt is short and factual; schema comes from API format."""
    prompt = build_prompt(OllamaTaskType.EVENT_CLASSIFICATION, {})
    assert len(prompt) > 0
    assert "JSON" in prompt
    assert "Context" in prompt


# --- get_format_for_task ---


def test_get_format_for_task_returns_schema_for_telemetry_summary() -> None:
    """get_format_for_task returns schema dict with type, properties, required, additionalProperties."""
    result = get_format_for_task(OllamaTaskType.TELEMETRY_SUMMARY)
    assert isinstance(result, dict)
    assert result == SCHEMA_TELEMETRY_OBJ
    assert result["type"] == "object"
    assert "properties" in result
    assert "required" in result
    assert result.get("additionalProperties") is False
    assert "status" in result["properties"]
    assert result["properties"]["status"].get("enum") == ["ok", "warn", "error"]
    assert "summary" in result["properties"]
    assert "concerns" in result["properties"]
    assert "recommendations" in result["properties"]


def test_get_format_for_task_returns_schema_for_event_classification() -> None:
    """get_format_for_task returns schema dict for event_classification."""
    result = get_format_for_task(OllamaTaskType.EVENT_CLASSIFICATION)
    assert isinstance(result, dict)
    assert result == SCHEMA_EVENT_OBJ
    assert result["type"] == "object"
    assert result.get("additionalProperties") is False
    assert "severity" in result["properties"]
    assert "category" in result["properties"]
    assert "likely_causes" in result["properties"]
    assert "recommended_checks" in result["properties"]


def test_get_format_for_task_returns_json_for_perception() -> None:
    """get_format_for_task returns 'json' for perception_detection."""
    result = get_format_for_task(OllamaTaskType.PERCEPTION_DETECTION)
    assert result == "json"


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
    raw = {
        "status": "ok",
        "summary": "All systems nominal.",
        "concerns": [],
        "recommendations": [],
    }
    result = parse_telemetry_summary_response(raw)
    assert result.summary == "All systems nominal."
    assert result.concerns == ()
    assert result.recommendations == ()


def test_parse_telemetry_summary_missing_fields() -> None:
    """Missing fields get safe defaults; empty summary normalized to Telemetry nominal."""
    raw: dict[str, Any] = {}
    result = parse_telemetry_summary_response(raw)
    assert result.status == "unknown"
    assert result.summary == "Telemetry nominal"
    assert result.concerns == ()
    assert result.recommendations == ()


def test_parse_telemetry_summary_none() -> None:
    """None input degrades safely; empty summary normalized."""
    result = parse_telemetry_summary_response(None)
    assert result.status == "unknown"
    assert result.summary == "Telemetry nominal"


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
    raw: dict[str, Any] = {
        "status": "ok",
        "summary": "All systems nominal.",
        "concerns": None,
    }
    result = parse_telemetry_summary_response(raw)
    assert result.summary == "All systems nominal."
    assert result.concerns == ()


def test_parse_telemetry_summary_string_recommendations() -> None:
    """String for list field normalizes to single-item tuple."""
    raw: dict[str, Any] = {
        "status": "ok",
        "summary": "Telemetry nominal",
        "recommendations": "check battery",
    }
    result = parse_telemetry_summary_response(raw)
    assert result.summary == "Telemetry nominal"
    assert result.recommendations == ("check battery",)


def test_parse_telemetry_summary_whitespace_string() -> None:
    """Whitespace-only string for list field normalizes to empty tuple."""
    raw: dict[str, Any] = {
        "status": "ok",
        "summary": "Telemetry nominal",
        "concerns": "   ",
    }
    result = parse_telemetry_summary_response(raw)
    assert result.concerns == ()


def test_parse_telemetry_summary_malformed_non_list() -> None:
    """Non-list non-string (e.g. int) for list field degrades to empty tuple."""
    raw: dict[str, Any] = {
        "status": "ok",
        "summary": "Telemetry nominal",
        "concerns": 123,
    }
    result = parse_telemetry_summary_response(raw)
    assert result.concerns == ()


def test_parse_telemetry_summary_str_schema_leakage() -> None:
    """Model schema leakage: literal 'str' for status or list items is filtered."""
    raw: dict[str, Any] = {
        "status": "str",
        "summary": "x",
        "concerns": ["str"],
        "recommendations": [],
    }
    result = parse_telemetry_summary_response(raw)
    assert result.status == "unknown"
    assert result.summary == "Telemetry nominal"
    assert result.concerns == ()
    assert result.recommendations == ()


def test_parse_telemetry_summary_invalid_status() -> None:
    """Invalid status (e.g. flight mode 'guiding') normalizes to unknown."""
    raw: dict[str, Any] = {
        "status": "guiding",
        "summary": "10 samples",
        "concerns": ["bat"],
        "recommendations": [],
    }
    result = parse_telemetry_summary_response(raw)
    assert result.status == "unknown"
    assert result.summary == "Telemetry nominal"


def test_parse_telemetry_summary_valid_statuses() -> None:
    """Valid status values ok, warn, error pass through."""
    for st in ("ok", "warn", "error"):
        raw: dict[str, Any] = {
            "status": st,
            "summary": "Telemetry nominal",
            "concerns": [],
            "recommendations": [],
        }
        result = parse_telemetry_summary_response(raw)
        assert result.status == st
        assert result.summary == "Telemetry nominal"


def test_parse_telemetry_summary_numeric_only_normalized() -> None:
    """Numeric-only summary is normalized to Telemetry nominal."""
    raw: dict[str, Any] = {
        "status": "ok",
        "summary": "10",
        "concerns": [],
        "recommendations": [],
    }
    result = parse_telemetry_summary_response(raw)
    assert result.summary == "Telemetry nominal"


def test_parse_telemetry_summary_measurement_only_normalized() -> None:
    """Measurement-only summaries (12%, 52m, 180deg, 12.1V) are normalized."""
    for weak in ("12%", "52m", "180deg", "12.1V"):
        raw: dict[str, Any] = {
            "status": "ok",
            "summary": weak,
            "concerns": [],
            "recommendations": [],
        }
        result = parse_telemetry_summary_response(raw)
        assert (
            result.summary == "Telemetry nominal"
        ), f"Expected normalization for {weak!r}"


def test_parse_telemetry_summary_single_token_normalized() -> None:
    """Single telemetry token (e.g. AUTO) is normalized to Telemetry nominal."""
    raw: dict[str, Any] = {
        "status": "ok",
        "summary": "AUTO",
        "concerns": [],
        "recommendations": [],
    }
    result = parse_telemetry_summary_response(raw)
    assert result.summary == "Telemetry nominal"


def test_parse_telemetry_summary_valid_short_sentence_accepted() -> None:
    """Valid short sentence passes through unchanged."""
    raw: dict[str, Any] = {
        "status": "ok",
        "summary": "Vehicle in AUTO with stable battery.",
        "concerns": [],
        "recommendations": [],
    }
    result = parse_telemetry_summary_response(raw)
    assert result.summary == "Vehicle in AUTO with stable battery."


def test_parse_telemetry_summary_neutral_nominal_accepted() -> None:
    """Neutral summaries Telemetry nominal and No immediate concerns pass through."""
    for neutral in ("Telemetry nominal", "No immediate concerns"):
        raw: dict[str, Any] = {
            "status": "ok",
            "summary": neutral,
            "concerns": [],
            "recommendations": [],
        }
        result = parse_telemetry_summary_response(raw)
        assert result.summary == neutral


def test_telemetry_summary_counters_accepted_meaningful() -> None:
    """Valid summary increments accepted_meaningful."""
    before = get_telemetry_summary_counts()
    parse_telemetry_summary_response(
        {
            "status": "ok",
            "summary": "Vehicle in AUTO with stable battery.",
            "concerns": [],
            "recommendations": [],
        }
    )
    after = get_telemetry_summary_counts()
    assert (
        after.get("accepted_meaningful", 0) - before.get("accepted_meaningful", 0) == 1
    )


def test_telemetry_summary_counters_normalized_to_nominal() -> None:
    """Weak summary increments normalized_to_nominal."""
    before = get_telemetry_summary_counts()
    parse_telemetry_summary_response(
        {"status": "ok", "summary": "10", "concerns": [], "recommendations": []}
    )
    after = get_telemetry_summary_counts()
    assert (
        after.get("normalized_to_nominal", 0) - before.get("normalized_to_nominal", 0)
        == 1
    )


def test_telemetry_summary_counters_parse_error() -> None:
    """None raw increments parse_error."""
    before = get_telemetry_summary_counts()
    parse_telemetry_summary_response(None)
    after = get_telemetry_summary_counts()
    assert after.get("parse_error", 0) - before.get("parse_error", 0) == 1


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


def test_parse_event_classification_str_schema_leakage() -> None:
    """Model schema leakage: literal 'str' for severity or list items is filtered."""
    raw: dict[str, Any] = {
        "severity": "str",
        "category": "x",
        "likely_causes": ["str"],
        "recommended_checks": [],
    }
    result = parse_event_classification_response(raw)
    assert result.severity == "info"
    assert result.likely_causes == ()
    assert result.recommended_checks == ()


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
async def test_task_service_ollama_sends_schema_in_format_for_telemetry_summary() -> (
    None
):
    """Ollama task service passes schema dict in format when calling generate_raw for telemetry."""
    ollama = OllamaAiService(
        base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
    )
    with patch.object(ollama, "generate_raw", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (
            '{"status":"ok","summary":"x","concerns":[],"recommendations":[]}'
        )
        svc = OllamaTaskService(provider="ollama", ollama_service=ollama)
        await svc.infer_task(OllamaTaskType.TELEMETRY_SUMMARY, {})
    mock_gen.assert_called_once()
    _, kwargs = mock_gen.call_args
    assert kwargs["format"] == SCHEMA_TELEMETRY_OBJ


@pytest.mark.asyncio
async def test_task_service_ollama_sends_schema_in_format_for_event_classification() -> (
    None
):
    """Ollama task service passes schema dict in format when calling generate_raw for events."""
    ollama = OllamaAiService(
        base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
    )
    with patch.object(ollama, "generate_raw", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = '{"severity":"info","category":"x","summary":"","likely_causes":[],"recommended_checks":[]}'
        svc = OllamaTaskService(provider="ollama", ollama_service=ollama)
        await svc.infer_task(OllamaTaskType.EVENT_CLASSIFICATION, {})
    mock_gen.assert_called_once()
    _, kwargs = mock_gen.call_args
    assert kwargs["format"] == SCHEMA_EVENT_OBJ


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
    assert result.summary == "Telemetry nominal"


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


# --- generate_raw backward-compat ---


@pytest.mark.asyncio
async def test_generate_raw_format_none_defaults_to_json() -> None:
    """generate_raw(prompt) or generate_raw(prompt, format=None) sends format 'json' in POST body."""
    captured_body: list[dict[str, Any]] = []
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "{}", "done": True}

    async def capture_post(*args: Any, **kwargs: Any) -> Any:
        captured_body.append(kwargs.get("json", {}))
        return mock_response

    mock_instance = AsyncMock()
    mock_instance.post = capture_post
    with patch("airautomatica.ai.ollama_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        service = OllamaAiService(
            base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
        )
        await service.generate_raw("test prompt")
    assert len(captured_body) == 1
    assert captured_body[0]["format"] == "json"
