"""Tests for MAVLink port detection and list (no double-open of live link)."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from airautomatica.api.routers.connection import _serial_settings_already_match
from airautomatica.api.server import create_app
from airautomatica.models.connection_state import ConnectionState
from airautomatica.runtime.telemetry_subsystem import TelemetryReconnectResult
from airautomatica.services.connection_state_store import (
    ConnectionStateStore,
)
from airautomatica.services.connection_state_store import (
    DetectionResult as StoreDetectionResult,
)
from airautomatica.services.state_store import StateStore
from airautomatica.telemetry.detector import (
    detect_on_port_skips_open_if_live_link,
    list_ports_with_status,
    scan_and_detect,
)


def test_list_ports_skips_probe_configured_port_when_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock backend + SERIAL_PORT set: do not call _probe_port_quick for that device."""
    monkeypatch.setenv("TELEMETRY_BACKEND", "mock")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyUSB0")
    monkeypatch.setenv("SERIAL_BAUD", "921600")
    calls: list[tuple[str, int, float]] = []

    def trace_probe(port: str, baud: int, timeout: float) -> tuple[bool, str | None]:
        calls.append((port, baud, timeout))
        return False, None

    with patch(
        "airautomatica.telemetry.detector.glob.glob",
        return_value=["/dev/ttyUSB0"],
    ):
        with patch(
            "airautomatica.telemetry.detector._probe_port_quick",
            side_effect=trace_probe,
        ):
            with patch("os.path.realpath", return_value="/canonical/usb"):
                rows = list_ports_with_status()

    assert calls == []
    usb = [p for p in rows if p.path == "/dev/ttyUSB0"]
    assert len(usb) == 1
    assert usb[0].status == "telemetry"
    assert usb[0].mavlink_active is True


def test_detect_on_port_skips_open_when_serial_live_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Serial backend on same port/baud returns without SerialTransport."""
    monkeypatch.setenv("TELEMETRY_BACKEND", "serial")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyUSB0")
    monkeypatch.setenv("SERIAL_BAUD", "921600")
    with patch("os.path.realpath", return_value="/rp/usb"):
        r = detect_on_port_skips_open_if_live_link(
            "/dev/ttyUSB0",
            921600,
            fallback_autopilot="inav",
            fallback_message="cached",
        )
    assert r is not None
    assert r.detected is True
    assert r.port == "/dev/ttyUSB0"
    assert r.baud == 921600
    assert r.autopilot == "inav"
    assert r.message == "cached"


def test_detect_on_port_skips_open_returns_none_wrong_baud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEMETRY_BACKEND", "serial")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyUSB0")
    monkeypatch.setenv("SERIAL_BAUD", "921600")
    with patch("os.path.realpath", return_value="/rp/usb"):
        r = detect_on_port_skips_open_if_live_link("/dev/ttyUSB0", 57600)
    assert r is None


def test_serial_settings_already_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEMETRY_BACKEND", "serial")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyUSB0")
    monkeypatch.setenv("SERIAL_BAUD", "921600")
    with patch("os.path.realpath", return_value="/x"):
        assert _serial_settings_already_match("/dev/ttyUSB0", 921600) is True
        assert _serial_settings_already_match("/dev/ttyUSB0", 57600) is False


def test_post_connection_detect_idempotent_no_save_no_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redetect same live serial port does not save_settings or reload telemetry."""
    monkeypatch.setenv("TELEMETRY_BACKEND", "serial")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyUSB0")
    monkeypatch.setenv("SERIAL_BAUD", "921600")

    store = StateStore()
    conn = ConnectionStateStore()
    conn.set_detection_result(
        StoreDetectionResult(
            detected=True,
            port="/dev/ttyUSB0",
            baud=921600,
            autopilot="ardupilot",
            message="prior",
            heartbeat_age_ms=None,
        )
    )
    conn.set_connection_state(ConnectionState.CONNECTED_ARDUPILOT)

    reload_mock = AsyncMock(
        return_value=TelemetryReconnectResult(success=True, backend_after="serial")
    )
    app = create_app(
        store,
        connection_store=conn,
        reload_telemetry_fn=reload_mock,
    )
    client = TestClient(app)

    with patch("os.path.realpath", return_value="/rp/usb"):
        with patch(
            "airautomatica.telemetry.detector.detect_on_port",
        ) as probe:
            probe.side_effect = AssertionError("probe should not run")
            with patch(
                "airautomatica.api.routers.connection.save_settings",
            ) as save_mock:
                r = client.post(
                    "/connection/detect",
                    json={"port": "/dev/ttyUSB0", "baud": 921600},
                )

    assert r.status_code == 200
    body = r.json()
    assert body["detected"] is True
    assert body["port"] == "/dev/ttyUSB0"
    save_mock.assert_not_called()
    reload_mock.assert_not_called()


def test_scan_and_detect_skips_live_serial_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full scan does not open the port already used by serial telemetry."""
    monkeypatch.setenv("TELEMETRY_BACKEND", "serial")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyUSB0")
    monkeypatch.setenv("SERIAL_BAUD", "921600")

    opens: list[str] = []

    class FakeTransport:
        def __init__(self, port: str, baud: int) -> None:
            self._port = port

        def connect(self) -> None:
            opens.append(self._port)

        def close(self) -> None:
            pass

        def read_message(self, timeout: float = 0.5):
            return None

    with patch(
        "airautomatica.telemetry.detector.glob.glob",
        return_value=["/dev/ttyUSB0"],
    ):
        with patch("os.path.realpath", return_value="/rp/usb"):
            with patch(
                "airautomatica.telemetry.detector.SerialTransport",
                FakeTransport,
            ):
                result = scan_and_detect()

    assert opens == []
    assert result.detected is False
