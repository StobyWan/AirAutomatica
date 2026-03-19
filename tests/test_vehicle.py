"""Tests for vehicle control subsystem."""

import pytest

from airautomatica.vehicle.control import (
    RoverControlMessage,
    validate_and_normalize,
)
from airautomatica.vehicle.control_store import (
    clear_control,
    get_last_control,
    update_control,
)
from airautomatica.vehicle.failsafe import is_stale, on_valid_command, reset


def test_validate_and_normalize_valid() -> None:
    """Valid message returns RoverControlMessage with deadband and clamping applied."""
    raw = {
        "timestamp": "2025-03-19T12:00:00.000Z",
        "seq": 42,
        "steering": 0.5,
        "throttle": -0.3,
        "pan": 0.0,
        "tilt": 0.0,
        "source": "gamepad",
        "mode": "rover",
    }
    msg = validate_and_normalize(raw)
    assert msg is not None
    assert msg.timestamp == "2025-03-19T12:00:00.000Z"
    assert msg.seq == 42
    assert msg.steering == 0.5
    assert msg.throttle == -0.3
    assert msg.source == "gamepad"
    assert msg.mode == "rover"


def test_validate_and_normalize_deadband() -> None:
    """Values near zero are deadbanded to 0."""
    raw = {
        "timestamp": "2025-03-19T12:00:00.000Z",
        "seq": 1,
        "steering": 0.02,
        "throttle": -0.03,
        "source": "keyboard",
        "mode": "rover",
    }
    msg = validate_and_normalize(raw)
    assert msg is not None
    assert msg.steering == 0.0
    assert msg.throttle == 0.0


def test_validate_and_normalize_clamped() -> None:
    """Values outside [-1, 1] are clamped."""
    raw = {
        "timestamp": "2025-03-19T12:00:00.000Z",
        "seq": 1,
        "steering": 2.0,
        "throttle": -1.5,
        "source": "api",
        "mode": "bench",
    }
    msg = validate_and_normalize(raw)
    assert msg is not None
    assert msg.steering == 1.0
    assert msg.throttle == -1.0


def test_validate_and_normalize_invalid_returns_none() -> None:
    """Invalid message returns None when types are wrong."""
    assert validate_and_normalize({"steering": "not_a_number"}) is None
    assert validate_and_normalize({"seq": "nan"}) is None


def test_control_store_update_and_get() -> None:
    """update_control stores valid message; get_last_control returns it."""
    clear_control()
    raw = {
        "timestamp": "2025-03-19T12:00:00.000Z",
        "seq": 1,
        "steering": 0.5,
        "throttle": 0.3,
        "source": "gamepad",
        "mode": "rover",
    }
    update_control(raw)
    last = get_last_control()
    assert last is not None
    assert last.steering == 0.5
    assert last.throttle == 0.3


def test_control_store_invalid_ignored() -> None:
    """Invalid message does not update store; valid message is preserved."""
    clear_control()
    valid = {
        "timestamp": "2025-03-19T12:00:00.000Z",
        "seq": 1,
        "steering": 0.5,
        "throttle": 0.3,
        "source": "gamepad",
        "mode": "rover",
    }
    update_control(valid)
    update_control({"steering": "not_a_number"})
    last = get_last_control()
    assert last is not None
    assert last.steering == 0.5


def test_control_store_clear() -> None:
    """clear_control removes stored message."""
    update_control(
        {
            "timestamp": "2025-03-19T12:00:00.000Z",
            "seq": 1,
            "steering": 0.5,
            "throttle": 0.3,
            "source": "gamepad",
            "mode": "rover",
        }
    )
    assert get_last_control() is not None
    clear_control()
    assert get_last_control() is None


def test_failsafe_stale_initially() -> None:
    """is_stale returns True when no valid command received."""
    reset()
    assert is_stale() is True


def test_failsafe_on_valid_command() -> None:
    """on_valid_command makes is_stale return False briefly."""
    reset()
    on_valid_command()
    assert is_stale() is False


def test_rover_control_message_to_dict() -> None:
    """RoverControlMessage.to_dict returns expected shape."""
    msg = RoverControlMessage(
        timestamp="2025-03-19T12:00:00.000Z",
        seq=42,
        steering=0.5,
        throttle=0.3,
        pan=0.0,
        tilt=0.0,
        source="gamepad",
        mode="rover",
    )
    d = msg.to_dict()
    assert d["timestamp"] == "2025-03-19T12:00:00.000Z"
    assert d["seq"] == 42
    assert d["steering"] == 0.5
    assert d["throttle"] == 0.3
    assert d["source"] == "gamepad"
    assert d["mode"] == "rover"
