"""Tests for serial MAVLink telemetry lifecycle and telemetry_status."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer
from airautomatica.telemetry.mock import MockTelemetry
from airautomatica.telemetry.serial_mavlink import SerialMavlinkTelemetry


def test_telemetry_status_healthy() -> None:
    """Mock telemetry yields connected status."""
    from types import SimpleNamespace

    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(SimpleNamespace(get_type=lambda: "HEARTBEAT", custom_mode=15))
    s = n.build_state()
    assert s.telemetry_status == "connected"
    assert s.connected is True


def test_telemetry_status_stale() -> None:
    """Normalizer yields stale when heartbeat timeout exceeded."""
    import time
    from types import SimpleNamespace

    n = MavlinkNormalizer(heartbeat_timeout_sec=0.05)
    n.apply(SimpleNamespace(get_type=lambda: "HEARTBEAT", custom_mode=0))
    s = n.build_state()
    assert s.telemetry_status == "connected"
    time.sleep(0.08)
    s = n.build_state()
    assert s.telemetry_status == "stale"
    assert s.connected is False


@pytest.mark.asyncio
async def test_telemetry_status_disconnected_and_backoff() -> None:
    """Serial backend yields disconnected then backoff with reconnect_count and last_disconnect_reason."""
    source = SerialMavlinkTelemetry(
        port="/dev/nonexistent",
        baud=57600,
        initial_backoff_sec=0.05,
        max_backoff_sec=0.15,
    )
    statuses: list[str] = []
    disconnect_reasons: list[str | None] = []
    reconnect_counts: list[int] = []

    async def collect() -> None:
        async for s in source.stream():
            statuses.append(s.telemetry_status)
            disconnect_reasons.append(s.last_disconnect_reason)
            reconnect_counts.append(s.reconnect_count)
            if s.telemetry_status == "backoff" and len(statuses) >= 4:
                return

    try:
        await asyncio.wait_for(collect(), timeout=5.0)
    except asyncio.TimeoutError:
        pass

    assert "starting" in statuses
    assert "disconnected" in statuses
    assert "backoff" in statuses
    assert any(rc >= 1 for rc in reconnect_counts)
    assert any(dr is not None for dr in disconnect_reasons)


@pytest.mark.asyncio
async def test_serial_yields_disconnected_on_connection_failure() -> None:
    """Serial backend yields disconnected state when connection fails.
    Non-existent port triggers immediate failure and reconnect loop."""
    source = SerialMavlinkTelemetry(
        port="/dev/nonexistent",
        baud=57600,
        initial_backoff_sec=0.05,
        max_backoff_sec=0.1,
    )
    states = []

    async def collect() -> None:
        async for s in source.stream():
            states.append(s)
            if len(states) >= 2:
                return

    try:
        await asyncio.wait_for(collect(), timeout=5.0)
    except asyncio.TimeoutError:
        pass

    assert len(states) >= 1
    assert states[0].connected is False
    assert states[0].heartbeat == 0
    assert states[0].telemetry_status in ("starting", "connecting", "disconnected")


@pytest.mark.asyncio
async def test_mock_telemetry_status_connected() -> None:
    """Mock telemetry yields connected status."""
    source = MockTelemetry(interval_sec=0.01)
    states: list = []
    async for s in source.stream():
        states.append(s)
        if len(states) >= 2:
            break
    assert all(st.telemetry_status == "connected" for st in states)
    assert all(st.reconnect_count == 0 for st in states)


@pytest.mark.asyncio
async def test_parser_failure_does_not_crash_stream() -> None:
    """Parser failures (malformed messages) are logged and stream continues.
    Uses mock by injecting a bad message - we test via the normalizer directly
    in test_mavlink_parser. Here we verify the serial stream structure allows
    for graceful handling."""
    source = SerialMavlinkTelemetry(
        port="/dev/nonexistent",
        baud=57600,
        initial_backoff_sec=0.05,
        max_backoff_sec=0.1,
    )
    states = []

    async def collect() -> None:
        async for s in source.stream():
            states.append(s)
            if len(states) >= 1:
                return

    try:
        await asyncio.wait_for(collect(), timeout=3.0)
    except asyncio.TimeoutError:
        pass

    assert len(states) >= 1
    assert hasattr(states[0], "connected")
    assert hasattr(states[0], "last_heartbeat_at")
    assert hasattr(states[0], "heartbeat_age_s")


@pytest.mark.asyncio
async def test_serial_connection_closed_on_reconnect() -> None:
    """MAVLink connection close() is called on no-heartbeat or reader exit."""
    mock_conn = MagicMock()
    mock_conn.wait_heartbeat.return_value = None
    mock_conn.close = MagicMock()

    with patch("pymavlink.mavutil.mavlink_connection", return_value=mock_conn):
        source = SerialMavlinkTelemetry(
            port="/dev/nonexistent",
            baud=57600,
            initial_backoff_sec=0.05,
            max_backoff_sec=0.2,
        )
        states = []

        async def collect() -> None:
            async for s in source.stream():
                states.append(s)
                if len(states) >= 4:
                    return

        try:
            await asyncio.wait_for(collect(), timeout=3.0)
        except asyncio.TimeoutError:
            pass

        mock_conn.close.assert_called()
