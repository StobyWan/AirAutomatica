"""Tests for AI service and normalized result."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airautomatica.ai import LmStudioAiService, MockAiService
from airautomatica.ai.models import AiResult
from airautomatica.models.state import AircraftState


@pytest.mark.asyncio
async def test_mock_service_returns_ai_result() -> None:
    """MockAiService.infer returns normalized AiResult."""
    service = MockAiService()
    result = await service.infer(None)
    assert isinstance(result, AiResult)
    assert result.label == "mock_ok"
    assert result.confidence == 0.99
    assert result.source_backend == "mock"
    assert "Mock inference" in result.summary


@pytest.mark.asyncio
async def test_mock_service_deterministic_with_state() -> None:
    """MockAiService uses aircraft state in summary."""
    service = MockAiService()
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
    result = await service.infer(state)
    assert "AUTO" in result.summary
    assert result.metadata is not None
    assert result.metadata["mode"] == "AUTO"


@pytest.mark.asyncio
async def test_mock_service_call_count_increments() -> None:
    """MockAiService increments call_count in metadata."""
    service = MockAiService()
    r1 = await service.infer(None)
    r2 = await service.infer(None)
    assert r1.metadata is not None
    assert r2.metadata is not None
    assert r1.metadata["call_count"] == 1
    assert r2.metadata["call_count"] == 2


@pytest.mark.asyncio
async def test_mock_service_custom_label_confidence() -> None:
    """MockAiService accepts custom label and confidence."""
    service = MockAiService(label="custom", confidence=0.5)
    result = await service.infer(None)
    assert result.label == "custom"
    assert result.confidence == 0.5


def test_ai_result_to_dict() -> None:
    """AiResult.to_dict serializes correctly."""
    result = AiResult(
        label="test",
        confidence=0.8,
        summary="Test summary",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
        metadata={"k": "v"},
    )
    d = result.to_dict()
    assert d["label"] == "test"
    assert d["confidence"] == 0.8
    assert d["summary"] == "Test summary"
    assert d["source_backend"] == "mock"
    assert "timestamp" in d
    assert d["metadata"] == {"k": "v"}


def test_ai_result_normalized_shape() -> None:
    """AiResult has required fields for mission logic."""
    result = AiResult(
        label="detection",
        confidence=0.95,
        summary="Object detected",
        source_backend="aihat",
        timestamp=datetime.now(timezone.utc),
        bbox=(10.0, 20.0, 50.0, 60.0),
        action="hold",
        metadata={"raw": "data"},
    )
    assert result.label == "detection"
    assert result.confidence == 0.95
    assert result.bbox == (10.0, 20.0, 50.0, 60.0)
    assert result.action == "hold"
    assert result.metadata == {"raw": "data"}


def test_mode_selection_mock() -> None:
    """Factory creates MockAiService for mode=mock."""
    from airautomatica.ai import MockAiService
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.setenv("AI_MODE", "mock")
        m.delenv("AI_BACKEND", raising=False)
        service = _create_ai_service()
    assert isinstance(service, MockAiService)


def test_mode_selection_lmstudio() -> None:
    """Factory creates LmStudioAiService for mode=lmstudio."""
    from airautomatica.ai import LmStudioAiService
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.setenv("AI_MODE", "lmstudio")
        m.delenv("AI_BACKEND", raising=False)
        service = _create_ai_service()
    assert isinstance(service, LmStudioAiService)


def test_mode_selection_aihat() -> None:
    """Factory creates AiHatAiService for mode=aihat."""
    from airautomatica.ai import AiHatAiService
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.setenv("AI_MODE", "aihat")
        m.delenv("AI_BACKEND", raising=False)
        service = _create_ai_service()
    assert isinstance(service, AiHatAiService)


def test_ai_backend_legacy_env() -> None:
    """AI_BACKEND env still works when AI_MODE not set."""
    from airautomatica.ai import LmStudioAiService
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.delenv("AI_MODE", raising=False)
        m.setenv("AI_BACKEND", "lmstudio")
        service = _create_ai_service()
    assert isinstance(service, LmStudioAiService)


@pytest.mark.asyncio
async def test_lmstudio_malformed_json_response() -> None:
    """LmStudioAiService returns error fallback when API returns invalid JSON."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    mock_post = AsyncMock(return_value=mock_response)
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    with patch("airautomatica.ai.lmstudio_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        service = LmStudioAiService(base_url="http://localhost:1234", model="test", timeout_sec=5.0)
        result = await service.infer(None)
    assert result.label == "error"
    assert result.confidence == 0.0
    assert result.source_backend == "lmstudio"
    assert result.metadata is not None
    assert result.metadata.get("parse_error") == "json"


@pytest.mark.asyncio
async def test_lmstudio_timeout_returns_fallback() -> None:
    """LmStudioAiService returns error fallback on timeout."""
    mock_post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    with patch("airautomatica.ai.lmstudio_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        service = LmStudioAiService(base_url="http://localhost:1234", model="test", timeout_sec=5.0)
        result = await service.infer(None)
    assert result.label == "error"
    assert result.confidence == 0.0
    assert result.source_backend == "lmstudio"
    assert result.metadata is not None
    assert result.metadata.get("error_type") == "timeout"


def test_ai_result_from_dict_normalization() -> None:
    """AiResult.from_dict normalizes partial/malformed dict with defaults."""
    result = AiResult.from_dict(
        {"label": "det", "confidence": 1.5, "summary": "ok", "bbox": [1, 2, 3, 4]},
        "lmstudio",
    )
    assert result.label == "det"
    assert result.confidence == 1.0  # clamped
    assert result.summary == "ok"
    assert result.source_backend == "lmstudio"
    assert result.bbox == (1.0, 2.0, 3.0, 4.0)
    assert result.action is None

    empty = AiResult.from_dict({}, "mock")
    assert empty.label == "unknown"
    assert empty.confidence == 0.0
    assert empty.summary == ""
    assert empty.bbox is None
    assert empty.action is None


def test_ai_result_fallback_shape() -> None:
    """Fallback AiResult from LmStudio has all required fields and valid types."""
    service = LmStudioAiService(base_url="http://x", model="m", timeout_sec=1.0)
    result = service._fallback_result("Test error", {"error": True, "error_type": "timeout"})
    assert result.label == "error"
    assert result.confidence == 0.0
    assert isinstance(result.summary, str)
    assert result.source_backend == "lmstudio"
    assert isinstance(result.timestamp, datetime)
    assert result.bbox is None
    assert result.action is None
    assert result.metadata == {"error": True, "error_type": "timeout"}
