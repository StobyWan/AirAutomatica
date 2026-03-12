"""Tests for mission logic AI result handling."""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from airautomatica.ai.models import AiResult
from airautomatica.models.state import AircraftState
from airautomatica.services.mission_logic import (
    MissionLogic,
    _normalize_label,
    get_perception_counts,
)
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


def test_reconfigure_updates_values() -> None:
    """reconfigure() updates min_confidence and duplicate_window_sec at runtime."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
        duplicate_window_sec=30.0,
    )
    result_person_06 = AiResult(
        label="person",
        confidence=0.6,
        summary="Detected",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
    )
    result_vehicle_04 = AiResult(
        label="vehicle",
        confidence=0.4,
        summary="Detected",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
    )
    result_vehicle_08 = AiResult(
        label="vehicle",
        confidence=0.8,
        summary="Detected",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result_person_06)
    assert persistence.insert_detection.call_count == 1
    logic.process_result(_make_state(), result_vehicle_04)
    assert persistence.insert_detection.call_count == 1
    logic.reconfigure(min_confidence=0.7)
    logic.process_result(_make_state(), result_vehicle_08)
    assert persistence.insert_detection.call_count == 2
    logic.reconfigure(min_confidence=0.3)
    result_building_04 = AiResult(
        label="building",
        confidence=0.4,
        summary="Detected",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result_building_04)
    assert persistence.insert_detection.call_count == 3


def test_reconfigure_clamps_min_confidence() -> None:
    """reconfigure() clamps min_confidence to 0-1 and takes effect on process_result."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="person",
        confidence=0.6,
        summary="Detected",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_called_once()
    logic.reconfigure(min_confidence=0.9)
    logic.process_result(_make_state(), result)
    assert persistence.insert_detection.call_count == 1


def test_low_confidence_ignored() -> None:
    """Low-confidence result is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
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
        session_ref=[1],
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
        session_ref=[1],
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
        session_ref=[1],
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
        session_ref=[1],
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
        session_ref=[1],
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


def test_placeholder_label_ollama_ignored() -> None:
    """Result with label='ollama' (unparseable placeholder) is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="ollama",
        confidence=0.9,
        summary="Unparseable content from Ollama",
        source_backend="ollama",
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
        session_ref=[1],
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
        session_ref=[1],
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
        session_ref=[1],
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


def test_normalize_label_spaces_underscores_hyphens() -> None:
    """Normalization collapses spaces, underscores, hyphens to single underscore."""
    assert _normalize_label("ground vehicle") == "GROUND_VEHICLE"
    assert _normalize_label("ground_vehicle") == "GROUND_VEHICLE"
    assert _normalize_label("ground-vehicle") == "GROUND_VEHICLE"
    assert _normalize_label("  person  ") == "PERSON"
    assert _normalize_label("") == ""


def test_none_label_not_persisted() -> None:
    """Result with label='none' (valid no-detection) is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.9,
    )
    result = AiResult(
        label="none",
        confidence=0.9,
        summary="No detection",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_heading_label_ignored() -> None:
    """Result with label='heading' (telemetry term) is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="heading",
        confidence=0.9,
        summary="Heading value",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_altitude_label_ignored() -> None:
    """Result with label='altitude' (telemetry term) is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="altitude",
        confidence=0.9,
        summary="Altitude value",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_unknown_label_rejected() -> None:
    """Result with label not in allowed vocabulary is not persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="cow",
        confidence=0.9,
        summary="Random label",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_ground_vehicle_normalized_accepted() -> None:
    """Result with label 'ground vehicle' (spaces) normalizes and is persisted."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="ground vehicle",
        confidence=0.8,
        summary="Ground vehicle detected",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_called_once()


def test_empty_label_no_response() -> None:
    """Result with empty label is not persisted (no_response)."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="",
        confidence=0.9,
        summary="Something",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    persistence.insert_detection.assert_not_called()


def test_perception_counts_accepted() -> None:
    """Accepted result increments accepted counter."""
    before = get_perception_counts()
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="person",
        confidence=0.8,
        summary="Person detected",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    after = get_perception_counts()
    assert after["accepted"] - before["accepted"] == 1


def test_perception_counts_suppressed() -> None:
    """Duplicate result increments suppressed counter."""
    before = get_perception_counts()
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
        duplicate_window_sec=30.0,
    )
    result = AiResult(
        label="person",
        confidence=0.8,
        summary="Person detected",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    state = _make_state()
    logic.process_result(state, result)
    logic.process_result(state, result)
    after = get_perception_counts()
    assert after["suppressed"] - before["suppressed"] == 1


def test_perception_counts_no_detection() -> None:
    """NONE label increments no_detection counter."""
    before = get_perception_counts()
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.9,
    )
    result = AiResult(
        label="none",
        confidence=0.9,
        summary="No detection",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    after = get_perception_counts()
    assert after["no_detection"] - before["no_detection"] == 1


def test_perception_counts_non_perception_label() -> None:
    """Disallowed label increments non_perception_label counter."""
    before = get_perception_counts()
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="battery",
        confidence=0.9,
        summary="Battery level",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    after = get_perception_counts()
    assert after["non_perception_label"] - before["non_perception_label"] == 1


def test_perception_counts_unknown_label() -> None:
    """Unknown label increments unknown_label counter."""
    before = get_perception_counts()
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.5,
    )
    result = AiResult(
        label="cow",
        confidence=0.9,
        summary="Random label",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    after = get_perception_counts()
    assert after["unknown_label"] - before["unknown_label"] == 1


def test_perception_counts_parse_error() -> None:
    """Placeholder label increments parse_error counter."""
    before = get_perception_counts()
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
        min_confidence=0.0,
    )
    result = AiResult(
        label="ollama",
        confidence=0.9,
        summary="Unparseable content",
        source_backend="ollama",
        timestamp=datetime.now(timezone.utc),
    )
    logic.process_result(_make_state(), result)
    after = get_perception_counts()
    assert after["parse_error"] - before["parse_error"] == 1


def test_duplicate_suppressed() -> None:
    """Same label within window is suppressed; insert_detection called once."""
    persistence = MagicMock()
    logic = MissionLogic(
        store=StateStore(),
        persistence=persistence,
        session_ref=[1],
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
        session_ref=[42],
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
        session_ref=[1],
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
        session_ref=[1],
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


@pytest.mark.asyncio
async def test_mission_loop_survives_ai_exception() -> None:
    """Mission loop continues after AI inference raises; infer is called again."""
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
    call_count = 0

    async def infer_raise_then_ok(_state):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("AI backend timeout")
        return ai_result

    ai_service = MagicMock()
    ai_service.infer = AsyncMock(side_effect=infer_raise_then_ok)

    persistence = MagicMock()
    logic = MissionLogic(
        store=store,
        ai_service=ai_service,
        persistence=persistence,
        session_ref=[1],
        interval_sec=0.05,
        ai_interval_sec=0.05,
        min_confidence=0.5,
    )
    task = asyncio.create_task(logic.run())
    await asyncio.sleep(0.25)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert call_count >= 2
    assert persistence.insert_detection.called


@pytest.mark.asyncio
async def test_run_skips_inference_when_no_session() -> None:
    """Mission logic does not call infer when session_ref is None."""
    store = StateStore()
    state = _make_state()
    store.update(state)

    ai_service = MagicMock()
    ai_service.infer = AsyncMock()

    persistence = MagicMock()
    logic = MissionLogic(
        store=store,
        ai_service=ai_service,
        persistence=persistence,
        session_ref=[None],
        interval_sec=0.05,
        ai_interval_sec=0.05,
        min_confidence=0.5,
    )
    task = asyncio.create_task(logic.run())
    await asyncio.sleep(0.25)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    ai_service.infer.assert_not_called()
    persistence.insert_detection.assert_not_called()
