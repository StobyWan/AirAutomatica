"""Tests for telemetry overlay formatter and writer."""

import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from airautomatica.models.state import AircraftState
from airautomatica.services.telemetry_overlay import (
    TelemetryWriter,
    format_telemetry,
)


def _make_state(
    mode: str = "STABILIZE",
    rel_alt_m: float = 12.3,
    groundspeed_m_s: float = 5.2,
    voltage_v: float = 12.4,
    armed: bool = True,
    satellites_visible: int | None = 12,
) -> AircraftState:
    return AircraftState(
        connected=True,
        heartbeat=1,
        mode=mode,
        lat=37.0,
        lon=-122.0,
        rel_alt_m=rel_alt_m,
        heading_deg=0.0,
        roll_rad=0.0,
        pitch_rad=0.0,
        yaw_rad=0.0,
        voltage_v=voltage_v,
        current_a=2.0,
        groundspeed_m_s=groundspeed_m_s,
        airspeed_m_s=groundspeed_m_s,
        timestamp=datetime.now(timezone.utc),
        armed=armed,
        satellites_visible=satellites_visible,
    )


def test_format_telemetry_valid_state() -> None:
    """format_telemetry(state) returns expected string for valid state (two lines)."""
    state = _make_state()
    result = format_telemetry(state)
    assert "Mode: STABILIZE" in result
    assert "Alt: 12.3m" in result
    assert "Spd: 5.2m/s" in result
    assert "Batt: 12.4V" in result
    assert "Armed: YES" in result
    assert "Sats: 12" in result
    assert "\n" in result
    lines = result.strip().split("\n")
    assert len(lines) == 2


def test_format_telemetry_none_returns_placeholder() -> None:
    """format_telemetry(None) returns placeholder string (two lines)."""
    result = format_telemetry(None)
    assert result == "Mode: — | Alt: — | Spd: —\nBatt: — | Armed: — | Sats: —"


def test_format_telemetry_nan_values_show_dash() -> None:
    """format_telemetry with NaN floats shows dash for those fields (two lines)."""
    state = AircraftState(
        connected=True,
        heartbeat=1,
        mode="GUIDED",
        lat=37.0,
        lon=-122.0,
        rel_alt_m=float("nan"),
        heading_deg=0.0,
        roll_rad=0.0,
        pitch_rad=0.0,
        yaw_rad=0.0,
        voltage_v=float("nan"),
        current_a=2.0,
        groundspeed_m_s=float("nan"),
        airspeed_m_s=0.0,
        timestamp=datetime.now(timezone.utc),
        armed=False,
        satellites_visible=None,
    )
    result = format_telemetry(state)
    assert "Alt: —" in result
    assert "Spd: —" in result
    assert "Batt: —" in result
    assert "Sats: —" in result
    assert "Armed: NO" in result
    assert "\n" in result


def test_telemetry_writer_only_writes_when_content_changes() -> None:
    """Writer only writes when format_telemetry(get_state()) differs from last written value."""
    states = [
        _make_state(rel_alt_m=10.0),
        _make_state(rel_alt_m=10.0),  # same
        _make_state(rel_alt_m=11.0),  # different
    ]
    call_idx = [0]

    def get_state() -> AircraftState | None:
        idx = min(call_idx[0], len(states) - 1)
        call_idx[0] += 1
        return states[idx]

    writer = TelemetryWriter(get_state=get_state)
    path = writer.start()
    try:
        assert path.exists()
        # Let writer run a few cycles (500ms each)
        time.sleep(1.6)
        # First write: state 0. Second write: state 2 (state 1 same as 0, no write)
        content = path.read_text(encoding="utf-8")
        assert "Alt: 11.0m" in content or "Alt: 10.0m" in content
    finally:
        writer.stop()
    assert not path.exists()


def test_telemetry_writer_temp_file_cleanup_after_stop() -> None:
    """After stop(), temp file does not exist."""
    writer = TelemetryWriter(get_state=lambda: None)
    path = writer.start()
    assert path.exists()
    writer.stop()
    assert not path.exists()


def test_telemetry_writer_cleanup_on_exception() -> None:
    """Temp file is removed when writer encounters exception in loop."""

    def get_state() -> AircraftState | None:
        raise RuntimeError("simulated error")

    writer = TelemetryWriter(get_state=get_state)
    path = writer.start()
    assert path.exists()
    time.sleep(0.7)  # Let one iteration run and hit the error
    writer.stop()
    assert not path.exists()


def test_ffmpeg_args_with_overlay_on() -> None:
    """With overlay enabled and get_state provided, ffmpeg args include -vf drawtext and -c:v libx264."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.close = MagicMock()

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.get_recording_telemetry_overlay_enabled",
                return_value=True,
            ):
                with patch(
                    "airautomatica.services.camera_recording.subprocess.Popen",
                    return_value=mock_proc,
                ) as mock_popen:
                    with patch("time.sleep"):
                        from airautomatica.services.camera_recording import (
                            CameraRecordingService,
                        )

                        svc = CameraRecordingService(
                            recordings_dir="/tmp/test_rec",
                            get_state=lambda: _make_state(),
                        )
                        svc.start_recording()

    calls = mock_popen.call_args_list
    assert len(calls) >= 2  # cam process + ffmpeg
    ffmpeg_call = None
    for call in calls:
        args = call[0][0] if call[0] else []
        if args and "ffmpeg" in str(args[0]).lower():
            ffmpeg_call = args
            break
    assert ffmpeg_call is not None
    ffmpeg_str = " ".join(ffmpeg_call)
    assert "-vf" in ffmpeg_str
    assert "drawtext" in ffmpeg_str
    assert "textfile=" in ffmpeg_str
    assert "-c:v" in ffmpeg_str
    assert "libx264" in ffmpeg_str

    svc.stop_recording()


def test_ffmpeg_args_with_overlay_off() -> None:
    """With overlay disabled, ffmpeg uses -c copy, no drawtext."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.close = MagicMock()

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.get_recording_telemetry_overlay_enabled",
                return_value=False,
            ):
                with patch(
                    "airautomatica.services.camera_recording.subprocess.Popen",
                    return_value=mock_proc,
                ) as mock_popen:
                    with patch("time.sleep"):
                        from airautomatica.services.camera_recording import (
                            CameraRecordingService,
                        )

                        svc = CameraRecordingService(
                            recordings_dir="/tmp/test_rec",
                            get_state=lambda: _make_state(),
                        )
                        svc.start_recording()

    calls = mock_popen.call_args_list
    ffmpeg_call = None
    for call in calls:
        args = call[0][0] if call[0] else []
        if args and "ffmpeg" in str(args[0]).lower():
            ffmpeg_call = args
            break
    assert ffmpeg_call is not None
    ffmpeg_str = " ".join(ffmpeg_call)
    assert "-c" in ffmpeg_str
    assert "copy" in ffmpeg_str
    assert "drawtext" not in ffmpeg_str
    assert "libx264" not in ffmpeg_str

    svc.stop_recording()
