"""Tests for VehicleConnectionManager adapter selection and state updates."""

import asyncio
from types import SimpleNamespace

import pytest

from airautomatica.telemetry.capabilities import DOWNGRADE_PARAM_READ_TIMEOUT
from airautomatica.telemetry.services.vehicle_connection_manager import (
    VehicleConnectionManager,
)


class MockTransport:
    """Mock transport with configurable message queue."""

    def __init__(self, messages: list) -> None:
        self._messages = list(messages)
        self._index = 0
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def close(self) -> None:
        self._connected = False

    def read_message(self, timeout: float = 2.0) -> object | None:
        if not self._connected:
            return None
        if self._index >= len(self._messages):
            return None
        msg = self._messages[self._index]
        self._index += 1
        return msg

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def connection(self) -> object | None:
        return (
            SimpleNamespace(target_system=1, target_component=1)
            if self._connected
            else None
        )


def make_heartbeat(autopilot: int = 3, custom_mode: int = 15) -> SimpleNamespace:
    m = SimpleNamespace()
    m.get_type = lambda: "HEARTBEAT"
    m.autopilot = autopilot
    m.custom_mode = custom_mode
    return m


def make_global_position(
    lat: int = 376213000, lon: int = -1223790000
) -> SimpleNamespace:
    m = SimpleNamespace()
    m.get_type = lambda: "GLOBAL_POSITION_INT"
    m.lat = lat
    m.lon = lon
    m.relative_alt = 50000
    m.hdg = 9000
    return m


@pytest.mark.asyncio
async def test_vcm_selects_ardupilot_adapter() -> None:
    """VehicleConnectionManager selects ArduPilot adapter when autopilot=3."""
    hb = make_heartbeat(autopilot=3)
    gps = make_global_position()
    transport = MockTransport([hb, gps, None, None])

    manager = VehicleConnectionManager(transport, heartbeat_timeout_sec=10.0)
    states = []
    async for state, cap in manager.run_connection_cycle():
        states.append((state, cap))
        if len(states) >= 3:
            break

    assert len(states) >= 2
    assert manager.selected_adapter == "ardupilot"
    assert manager.capability_info is not None
    assert manager.capability_info.profile.supports_message_interval is True
    assert states[0][0].mode == "GUIDED"
    assert abs(states[1][0].lat - 37.6213) < 1e-4


@pytest.mark.asyncio
async def test_vcm_selects_inav_adapter() -> None:
    """VehicleConnectionManager selects INAV adapter when autopilot=13."""
    hb = make_heartbeat(autopilot=13, custom_mode=4)
    transport = MockTransport([hb, None, None])

    manager = VehicleConnectionManager(transport, heartbeat_timeout_sec=10.0)
    states = []
    async for state, cap in manager.run_connection_cycle():
        states.append((state, cap))
        if len(states) >= 2:
            break

    assert manager.selected_adapter == "inav"
    assert manager.capability_info is not None
    assert manager.capability_info.profile.supports_message_interval is False
    assert states[0][0].mode == "NAV_POSHOLD"


@pytest.mark.asyncio
async def test_vcm_selects_generic_adapter() -> None:
    """VehicleConnectionManager selects Generic adapter for unknown autopilot."""
    hb = make_heartbeat(autopilot=0, custom_mode=10)
    transport = MockTransport([hb, None, None])

    manager = VehicleConnectionManager(transport, heartbeat_timeout_sec=10.0)
    states = []
    async for state, cap in manager.run_connection_cycle():
        states.append((state, cap))
        if len(states) >= 2:
            break

    assert manager.selected_adapter == "generic"
    assert manager.capability_info is not None
    assert "Unknown" in manager.capability_info.profile.notes
    assert states[0][0].mode == "10"


@pytest.mark.asyncio
async def test_vcm_raises_on_no_heartbeat() -> None:
    """VehicleConnectionManager raises when no HEARTBEAT within timeout."""
    transport = MockTransport([None, None, None])

    manager = VehicleConnectionManager(transport, heartbeat_timeout_sec=0.1)
    with pytest.raises(RuntimeError, match="No HEARTBEAT"):
        async for _ in manager.run_connection_cycle():
            pass


@pytest.mark.asyncio
async def test_vcm_capability_info_includes_downgrade_reasons() -> None:
    """CapabilityInfo includes downgrade_reasons when safe_probe times out."""
    hb = make_heartbeat(autopilot=3)
    # No PARAM_VALUE in queue -> ArduPilotAdapter.safe_probe will timeout
    transport = MockTransport([hb, None, None, None])

    manager = VehicleConnectionManager(transport, heartbeat_timeout_sec=10.0)
    states = []
    async for state, cap in manager.run_connection_cycle():
        states.append((state, cap))
        if len(states) >= 1:
            break

    assert manager.capability_info is not None
    assert manager.capability_info.downgrade_reasons == (DOWNGRADE_PARAM_READ_TIMEOUT,)
