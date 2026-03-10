"""Tests for CommandPolicy scaffold."""

from datetime import datetime, timezone

from airautomatica.ai.models import AiResult
from airautomatica.commands import CommandPolicy
from airautomatica.models.state import AircraftState


def _make_state(
    connected: bool = True,
    heartbeat_age_s: float = 0.5,
) -> AircraftState:
    now = datetime.now(timezone.utc)
    return AircraftState(
        connected=connected,
        heartbeat=1,
        mode="GUIDED",
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
        timestamp=now,
        last_heartbeat_at=now,
        heartbeat_age_s=heartbeat_age_s,
    )


def test_blocked_when_disabled() -> None:
    """command_enabled=False returns (False, 'commands_disabled')."""
    policy = CommandPolicy(
        command_enabled=False,
        allowed_commands=frozenset({"DO_SET_MODE"}),
    )
    allowed, reason = policy.evaluate("DO_SET_MODE", _make_state())
    assert allowed is False
    assert reason == "commands_disabled"


def test_blocked_when_telemetry_not_connected() -> None:
    """state.connected=False, require_connected=True returns (False, 'telemetry_not_connected')."""
    policy = CommandPolicy(
        command_enabled=True,
        allowed_commands=frozenset({"DO_SET_MODE"}),
        require_connected=True,
    )
    state = _make_state(connected=False)
    allowed, reason = policy.evaluate("DO_SET_MODE", state)
    assert allowed is False
    assert reason == "telemetry_not_connected"


def test_blocked_when_command_not_allowed() -> None:
    """Command not in allowed_commands returns (False, 'command_not_allowed')."""
    policy = CommandPolicy(
        command_enabled=True,
        allowed_commands=frozenset({"DO_SET_MODE"}),
    )
    allowed, reason = policy.evaluate("MAV_CMD_NAV_TAKEOFF", _make_state())
    assert allowed is False
    assert reason == "command_not_allowed"


def test_blocked_when_stale_heartbeat() -> None:
    """heartbeat_age_s > heartbeat_max_age_sec returns (False, 'stale_heartbeat')."""
    policy = CommandPolicy(
        command_enabled=True,
        allowed_commands=frozenset({"DO_SET_MODE"}),
        heartbeat_max_age_sec=5.0,
    )
    state = _make_state(heartbeat_age_s=10.0)
    allowed, reason = policy.evaluate("DO_SET_MODE", state)
    assert allowed is False
    assert reason == "stale_heartbeat"


def test_allowed_when_conditions_pass() -> None:
    """Command in allowed, connected, fresh heartbeat returns (True, 'ok')."""
    policy = CommandPolicy(
        command_enabled=True,
        allowed_commands=frozenset({"DO_SET_MODE"}),
    )
    allowed, reason = policy.evaluate("DO_SET_MODE", _make_state())
    assert allowed is True
    assert reason == "ok"


def test_blocked_when_low_confidence() -> None:
    """require_min_confidence=0.8, ai_result.confidence=0.5 returns (False, 'low_confidence')."""
    policy = CommandPolicy(
        command_enabled=True,
        allowed_commands=frozenset({"DO_SET_MODE"}),
        require_min_confidence=0.8,
    )
    ai_result = AiResult(
        label="person",
        confidence=0.5,
        summary="Person detected",
        source_backend="mock",
        timestamp=datetime.now(timezone.utc),
    )
    allowed, reason = policy.evaluate("DO_SET_MODE", _make_state(), ai_result=ai_result)
    assert allowed is False
    assert reason == "low_confidence"


def test_blocked_when_no_state() -> None:
    """state=None returns (False, 'no_state')."""
    policy = CommandPolicy(
        command_enabled=True,
        allowed_commands=frozenset({"DO_SET_MODE"}),
    )
    allowed, reason = policy.evaluate("DO_SET_MODE", None)
    assert allowed is False
    assert reason == "no_state"
