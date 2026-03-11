"""Tests for AI service and normalized result."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airautomatica.ai import (
    AiHatAiService,
    ComposedAiService,
    MockAiService,
    OllamaAiService,
)
from airautomatica.ai.models import AiResult, create_error_fallback
from airautomatica.ai.service import AiService
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


def test_default_provider_is_ollama() -> None:
    """Factory creates OllamaAiService when no provider/mode set (canonical default)."""
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.delenv("LOCAL_LLM_PROVIDER", raising=False)
        m.delenv("AI_MODE", raising=False)
        m.delenv("AI_BACKEND", raising=False)
        m.delenv("AI_HAT_ENABLED", raising=False)
        service = _create_ai_service()
    assert isinstance(service, OllamaAiService)


def test_mode_selection_mock() -> None:
    """Factory creates MockAiService for mode=mock (no AI HAT)."""
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.setenv("AI_MODE", "mock")
        m.delenv("AI_BACKEND", raising=False)
        m.delenv("LOCAL_LLM_PROVIDER", raising=False)
        m.delenv("AI_HAT_ENABLED", raising=False)
        service = _create_ai_service()
    assert isinstance(service, MockAiService)


def test_provider_selection_ollama() -> None:
    """Factory creates OllamaAiService for LOCAL_LLM_PROVIDER=ollama or AI_MODE=ollama (no AI HAT)."""
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.delenv("AI_BACKEND", raising=False)
        m.delenv("AI_HAT_ENABLED", raising=False)
        m.setenv("LOCAL_LLM_PROVIDER", "ollama")
        m.delenv("AI_MODE", raising=False)
        service = _create_ai_service()
    assert isinstance(service, OllamaAiService)

    with pytest.MonkeyPatch.context() as m:
        m.delenv("LOCAL_LLM_PROVIDER", raising=False)
        m.delenv("AI_HAT_ENABLED", raising=False)
        m.setenv("AI_MODE", "ollama")
        m.delenv("AI_BACKEND", raising=False)
        service = _create_ai_service()
    assert isinstance(service, OllamaAiService)


def test_lmstudio_maps_to_mock(caplog: pytest.LogCaptureFixture) -> None:
    """LOCAL_LLM_PROVIDER=lmstudio or AI_MODE/AI_BACKEND=lmstudio resolve to MockAiService with warning."""
    import airautomatica.config as config_module
    from airautomatica.main import _create_ai_service

    config_module._lmstudio_warned = False
    with pytest.MonkeyPatch.context() as m:
        m.setenv("LOCAL_LLM_PROVIDER", "lmstudio")
        m.delenv("AI_MODE", raising=False)
        m.delenv("AI_BACKEND", raising=False)
        m.delenv("AI_HAT_ENABLED", raising=False)
        service = _create_ai_service()
    assert isinstance(service, MockAiService)
    assert "lmstudio is no longer supported" in caplog.text

    config_module._lmstudio_warned = False
    with pytest.MonkeyPatch.context() as m:
        m.delenv("LOCAL_LLM_PROVIDER", raising=False)
        m.setenv("AI_MODE", "lmstudio")
        m.delenv("AI_BACKEND", raising=False)
        m.delenv("AI_HAT_ENABLED", raising=False)
        service = _create_ai_service()
    assert isinstance(service, MockAiService)

    config_module._lmstudio_warned = False
    with pytest.MonkeyPatch.context() as m:
        m.delenv("LOCAL_LLM_PROVIDER", raising=False)
        m.delenv("AI_MODE", raising=False)
        m.setenv("AI_BACKEND", "lmstudio")
        m.delenv("AI_HAT_ENABLED", raising=False)
        service = _create_ai_service()
    assert isinstance(service, MockAiService)


def test_mode_selection_aihat() -> None:
    """Factory creates ComposedAiService (mock+aihat) for mode=aihat."""
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.setenv("AI_MODE", "aihat")
        m.delenv("AI_BACKEND", raising=False)
        m.delenv("LOCAL_LLM_PROVIDER", raising=False)
        m.delenv("AI_HAT_ENABLED", raising=False)
        service = _create_ai_service()
    assert isinstance(service, ComposedAiService)


def test_ai_result_from_dict_normalization() -> None:
    """AiResult.from_dict normalizes partial/malformed dict with defaults."""
    result = AiResult.from_dict(
        {"label": "det", "confidence": 1.5, "summary": "ok", "bbox": [1, 2, 3, 4]},
        "ollama",
    )
    assert result.label == "det"
    assert result.confidence == 1.0  # clamped
    assert result.summary == "ok"
    assert result.source_backend == "ollama"
    assert result.bbox == (1.0, 2.0, 3.0, 4.0)
    assert result.action is None

    empty = AiResult.from_dict({}, "mock")
    assert empty.label == "unknown"
    assert empty.confidence == 0.0
    assert empty.summary == ""
    assert empty.bbox is None
    assert empty.action is None


def test_ai_result_fallback_shape() -> None:
    """create_error_fallback returns AiResult with all required fields and valid types."""
    result = create_error_fallback(
        "Test error", {"error": True, "error_type": "timeout"}, "ollama"
    )
    assert result.label == "error"
    assert result.confidence == 0.0
    assert isinstance(result.summary, str)
    assert result.source_backend == "ollama"
    assert isinstance(result.timestamp, datetime)
    assert result.bbox is None
    assert result.action is None
    assert result.metadata == {"error": True, "error_type": "timeout"}


@pytest.mark.asyncio
async def test_ollama_valid_json_response() -> None:
    """OllamaAiService parses valid JSON from response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "response": '{"label":"person","confidence":0.9,"summary":"Person detected"}',
        "done": True,
    }
    mock_post = AsyncMock(return_value=mock_response)
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    with patch("airautomatica.ai.ollama_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        service = OllamaAiService(
            base_url="http://127.0.0.1:11434", model="gemma3:1b", timeout_sec=5.0
        )
        result = await service.infer(None)
    assert result.label == "person"
    assert result.confidence == 0.9
    assert result.summary == "Person detected"
    assert result.source_backend == "ollama"


@pytest.mark.asyncio
async def test_ollama_request_includes_num_thread() -> None:
    """Ollama generate request includes options.num_thread from config."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "{}", "done": True}
    mock_post = AsyncMock(return_value=mock_response)
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    with patch("airautomatica.ai.ollama_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        with patch(
            "airautomatica.ai.ollama_service.get_ollama_num_thread", return_value=4
        ):
            service = OllamaAiService(
                base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
            )
            await service.generate_raw("hello")
    call_kwargs = mock_post.call_args[1]
    payload = call_kwargs["json"]
    assert "options" in payload
    assert payload["options"]["num_thread"] == 4


@pytest.mark.asyncio
async def test_ollama_malformed_response() -> None:
    """OllamaAiService returns fallback when API returns invalid JSON."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    mock_post = AsyncMock(return_value=mock_response)
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    with patch("airautomatica.ai.ollama_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        service = OllamaAiService(
            base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
        )
        result = await service.infer(None)
    assert result.label == "error"
    assert result.confidence == 0.0
    assert result.source_backend == "ollama"
    assert result.metadata is not None
    assert result.metadata.get("parse_error") == "json"


@pytest.mark.asyncio
async def test_ollama_timeout_returns_fallback() -> None:
    """OllamaAiService returns fallback on timeout."""
    mock_post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    with patch("airautomatica.ai.ollama_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        service = OllamaAiService(
            base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
        )
        result = await service.infer(None)
    assert result.label == "error"
    assert result.confidence == 0.0
    assert result.source_backend == "ollama"
    assert result.metadata is not None
    assert result.metadata.get("error_type") == "timeout"


@pytest.mark.asyncio
async def test_ollama_network_error_returns_fallback() -> None:
    """OllamaAiService returns fallback on network error."""
    mock_post = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    with patch("airautomatica.ai.ollama_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        service = OllamaAiService(
            base_url="http://127.0.0.1:11434", model="test", timeout_sec=5.0
        )
        result = await service.infer(None)
    assert result.label == "error"
    assert result.confidence == 0.0
    assert result.source_backend == "ollama"
    assert result.metadata is not None
    assert result.metadata.get("error_type") == "network"


def test_mock_plus_aihat() -> None:
    """Factory creates ComposedAiService when AI_HAT_ENABLED and provider=mock."""
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.setenv("AI_MODE", "mock")
        m.setenv("AI_HAT_ENABLED", "1")
        m.delenv("AI_BACKEND", raising=False)
        service = _create_ai_service()
    assert isinstance(service, ComposedAiService)


def test_ollama_plus_aihat() -> None:
    """Factory creates ComposedAiService when AI_HAT_ENABLED and provider=ollama."""
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.setenv("LOCAL_LLM_PROVIDER", "ollama")
        m.setenv("AI_HAT_ENABLED", "1")
        m.delenv("AI_MODE", raising=False)
        service = _create_ai_service()
    assert isinstance(service, ComposedAiService)


def test_aihat_unavailable_fallback() -> None:
    """When AI_HAT_ENABLED=false, factory returns base provider only (no composition)."""
    from airautomatica.main import _create_ai_service

    with pytest.MonkeyPatch.context() as m:
        m.setenv("AI_MODE", "mock")
        m.setenv("AI_HAT_ENABLED", "0")
        m.delenv("LOCAL_LLM_PROVIDER", raising=False)
        service = _create_ai_service()
    assert isinstance(service, MockAiService)

    with pytest.MonkeyPatch.context() as m:
        m.setenv("LOCAL_LLM_PROVIDER", "ollama")
        m.setenv("AI_HAT_ENABLED", "false")
        m.delenv("AI_MODE", raising=False)
        service = _create_ai_service()
    assert isinstance(service, OllamaAiService)


@pytest.mark.asyncio
async def test_composed_uses_base_when_aihat_scaffold() -> None:
    """ComposedAiService returns base result when AI HAT returns scaffold placeholder."""
    base = MockAiService()
    aihat = AiHatAiService(model_name="x", device="y")
    composed = ComposedAiService(base_ai_service=base, aihat_service=aihat)
    result = await composed.infer(None)
    assert result.source_backend == "mock"
    assert "Mock inference" in result.summary


@pytest.mark.asyncio
async def test_composed_uses_aihat_when_meaningful() -> None:
    """ComposedAiService returns AI HAT result when it produces meaningful output."""
    base = MockAiService()
    aihat = MagicMock(spec=AiService)
    aihat.infer = AsyncMock(
        return_value=AiResult(
            label="person",
            confidence=0.95,
            summary="Person detected",
            source_backend="aihat",
            timestamp=datetime.now(timezone.utc),
        )
    )
    composed = ComposedAiService(base_ai_service=base, aihat_service=aihat)
    result = await composed.infer(None)
    assert result.source_backend == "aihat"
    assert result.label == "person"
    assert result.confidence == 0.95
