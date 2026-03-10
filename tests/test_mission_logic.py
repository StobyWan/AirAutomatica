"""Tests for mission logic AI result handling."""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from airautomatica.ai.models import AiResult
from airautomatica.models.state import AircraftState
from airautomatica.services.mission_logic import MissionLogic
from airautomatica.services.state_store import StateStore


def _make_state(
    lat: float = 37.0, lon: float = -122.0, rel_alt_m: float = 100.0
) -> AircraftState:
    return AircraftState(
        connected=True,
        heartbeat=1,
        mode="AUTO",
        lat=lat,
        lon=lon,
        rel_alt_m=rel_alt_m,
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


def test_low_confidence_ignored() -> None:
    """Low-confidence result is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
    )
    result = AiResult(
        label="person",
        confidence=0.3,
        summary="Low confidence detection",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_error_label_ignored() -> None:
    """Error-shaped result (label=error) is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.0,
    )
    result = AiResult(
        label="error",
        confidence=0.0,
        summary="LM Studio timeout",
        source_backend="lmstudio",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_empty_summary_ignored() -> None:
    """Result with empty summary is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
    )
    result = AiResult(
        label="person",
        confidence=0.9,
        summary="",
        source_backend="lmstudio",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_no_response_summary_ignored() -> None:
    """Result with summary 'No response' is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
    )
    result = AiResult(
        label="person",
        confidence=0.9,
        summary="No response",
        source_backend="lmstudio",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_raw_length_zero_ignored() -> None:
    """Result with metadata.raw_length=0 is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
    )
    result = AiResult(
        label="person",
        confidence=0.9,
        summary="Person detected",
        source_backend="lmstudio",
        timestamp=datetime.now(timezone.utc),
        metadata={"raw_length": 0},
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_placeholder_label_lmstudio_ignored() -> None:
    """Result with label='lmstudio' (generic placeholder) is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
    )
    result = AiResult(
        label="lmstudio",
        confidence=0.9,
        summary="Some content from LLM",
        source_backend="lmstudio",
        timestamp=datetime.now(timezone.utc),
        metadata={"raw_length": 50},
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_guided_label_ignored() -> None:
    """Result with label='GUIDED' (ArduPilot mode) is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
    )
    result = AiResult(
        label="GUIDED",
        confidence=0.9,
        summary="In guided mode",
        source_backend="lmstudio",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_device_status_label_ignored() -> None:
    """Result with label='device_status' is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
    )
    result = AiResult(
        label="device_status",
        confidence=0.9,
        summary="Device status update",
        source_backend="lmstudio",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_battery_label_ignored() -> None:
    """Result with label='battery' is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
    )
    result = AiResult(
        label="battery",
        confidence=0.9,
        summary="Battery level",
        source_backend="lmstudio",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_duplicate_suppressed() -> None:
    """Same label within window is suppressed; insert_detection called once."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
        duplicate_window_sec=30.0,
    )
    result = AiResult(
        label="person",
        confidence=0.8,
        summary="Person detected",
        source_backend="aihat",
        timestamp=datetime.now(timezone.utc),
    )
    state = _make_state()
    logic.process_result(state, result)
    logic.process_result(state, result)
    assert persistence.insert_detection.call_count == 1


def test_accepted_detection_persisted() -> None:
    """Meaningful result is persisted with correct args."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=42,
        min_confidence=0.5,
    )
    result = AiResult(
        label="person",
        confidence=0.8,
        summary="Person detected",
        source_backend="aihat",
        timestamp=datetime.now(timezone.utc),
    )
    state = _make_state(lat=38.0, lon=-121.0, rel_alt_m=50.0)
    logic.process_result(state, result)
    persistence.insert_detection.assert_called_once_with(
        42,
        result,
        38.0,
        -121.0,
        50.0,
    )


def test_duplicate_after_window_persisted() -> None:
    """Same label after window expiry is accepted; insert_detection called twice."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_id=1,
        min_confidence=0.5,
        duplicate_window_sec=0.1,
    )
    result = AiResult(
        label="vehicle",
        confidence=0.9,
        summary="Vehicle detected",
        source_backend="aihat",
        timestamp=datetime.now(timezone.utc),
    )
    state = _make_state()
    logic.process_result(state, result)
    time.sleep(0.15)
    logic.process_result(state, result)
    assert persistence.insert_detection.call_count == 2


@pytest.mark.asyncio
async def test_run_calls_process_result() -> None:
    """Mission logic run loop calls process_result with AI result."""
    store = StateStore()
    state = _make_state()
    store.update(state)

    ai_result = AiResult(
        label="person",
        confidence=0.9,
        summary="Person",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
    )
    ai_service = MagicMock()
    ai_service.infer = AsyncMock(return_value=ai_result)

    persistence = MagicMock()
    logic = MissionLogic(
        store=store,
        ai_service=ai_service,
        persistence=persistence,
        session_id=1,
        interval_sec=10.0,
        ai_interval_sec=0.1,
        min_confidence=0.5,
    )
    task = asyncio.create_task(logic.run())
    await asyncio.sleep(0.25)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert ai_service.infer.called
    assert persistence.insert_detection.called
