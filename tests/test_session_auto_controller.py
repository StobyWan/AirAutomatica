"""Tests for SessionAutoController (arm/disarm session auto)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from airautomatica.models.connection_state import ConnectionState
from airautomatica.models.state import AircraftState
from airautomatica.services.connection_state_store import ConnectionStateStore
from airautomatica.services.session_auto_controller import SessionAutoController


def _aircraft_state(**kwargs: object) -> AircraftState:
    """Minimal AircraftState for controller tests."""
    now = datetime.now(timezone.utc)
    base: dict = {
        "connected": True,
        "heartbeat": 1,
        "mode": "MANUAL",
        "lat": 0.0,
        "lon": 0.0,
        "rel_alt_m": 0.0,
        "heading_deg": 0.0,
        "roll_rad": 0.0,
        "pitch_rad": 0.0,
        "yaw_rad": 0.0,
        "voltage_v": 12.0,
        "current_a": 0.0,
        "groundspeed_m_s": 0.0,
        "airspeed_m_s": 0.0,
        "timestamp": now,
        "last_heartbeat_at": now,
        "heartbeat_age_s": 0.0,
        "telemetry_status": "connected",
        "reconnect_count": 0,
        "last_disconnect_reason": None,
        "armed": False,
        "climb_rate_m_s": 0.0,
    }
    base.update(kwargs)
    return AircraftState(**base)


@pytest.fixture
def session_auto_harness() -> tuple[MagicMock, list[int | None], SessionAutoController]:
    persistence = MagicMock()
    persistence.start_session.return_value = 100
    session_ref: list[int | None] = [99]
    conn_store = ConnectionStateStore()
    conn_store.set_connection_state(ConnectionState.CONNECTED_ARDUPILOT)
    ctrl = SessionAutoController(
        persistence=persistence,
        session_ref=session_ref,
        connection_store=conn_store,
        get_enabled_fn=lambda: True,
        debounce_sec=2.5,
    )
    return persistence, session_ref, ctrl


def test_disarm_debounce_resets_when_telemetry_untrustworthy(
    session_auto_harness: tuple[MagicMock, list[int | None], SessionAutoController],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a serial drop, disarm debounce must restart — not use pre-drop monotonic time."""
    persistence, _session_ref, ctrl = session_auto_harness

    tick = [0.0, 1.0, 100.0, 103.0]
    i = [0]

    def fake_mono() -> float:
        v = tick[i[0]]
        i[0] += 1
        return v

    monkeypatch.setattr(
        "airautomatica.services.session_auto_controller.time.monotonic", fake_mono
    )

    ctrl.maybe_auto_start_stop(_aircraft_state(connected=True, armed=False))
    assert persistence.end_session.call_count == 0

    ctrl.maybe_auto_start_stop(
        _aircraft_state(
            connected=False,
            armed=False,
            telemetry_status="disconnected",
        )
    )
    assert persistence.end_session.call_count == 0

    ctrl.maybe_auto_start_stop(_aircraft_state(connected=True, armed=False))
    assert persistence.end_session.call_count == 0

    ctrl.maybe_auto_start_stop(_aircraft_state(connected=True, armed=False))
    assert persistence.end_session.call_count == 1
    persistence.end_session.assert_called_once_with(99)


def test_untrustworthy_telemetry_does_not_update_last_armed(
    session_auto_harness: tuple[MagicMock, list[int | None], SessionAutoController],
) -> None:
    """Disconnect samples must not flip _last_armed (avoids spurious arm edge on reconnect)."""
    _persistence, _session_ref, ctrl = session_auto_harness
    ctrl._last_armed = True

    ctrl.maybe_auto_start_stop(
        _aircraft_state(
            connected=False,
            armed=False,
            telemetry_status="disconnected",
        )
    )
    assert ctrl._last_armed is True
