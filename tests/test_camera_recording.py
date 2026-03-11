"""Tests for camera recording service and auto controller."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from airautomatica.models.state import AircraftState
from airautomatica.services.camera_recording import (
    CameraRecordingService,
    RecordingAutoController,
)


@pytest.fixture
def recordings_dir(tmp_path: Path) -> str:
    """Temp directory for recordings in tests."""
    return str(tmp_path / "recordings")


def test_recording_state_idle(recordings_dir: str) -> None:
    """Initial state is not recording."""
    svc = CameraRecordingService(recordings_dir=recordings_dir)
    state = svc.get_recording_state()
    assert state.recording is False
    assert state.output_file is None
    assert state.started_at is None


def test_start_recording_when_idle(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Start returns recording state when idle (libcamera-vid, .h264)."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("time.sleep"):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                state, err = svc.start_recording()
    assert err is None
    assert state.recording is True
    assert state.output_file is not None
    assert state.output_file.endswith(".h264")
    assert state.started_at is not None


def test_start_recording_when_already_recording(
    monkeypatch: pytest.MonkeyPatch,
    recordings_dir: str,
) -> None:
    """Start when already recording returns same state, no duplicate process."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ) as mock_popen:
            with patch("time.sleep"):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                state1, err1 = svc.start_recording()
                state2, err2 = svc.start_recording()
    assert err1 is None
    assert err2 is None
    assert state1.recording is True
    assert state2.recording is True
    assert state1.output_file == state2.output_file
    assert mock_popen.call_count == 1


def test_stop_recording_when_recording(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Stop when recording returns idle state."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("time.sleep"):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                svc.start_recording()
    state, err = svc.stop_recording()
    assert err is None
    assert state.recording is False
    assert state.output_file is None
    assert state.started_at is None


def test_stop_recording_when_idle(recordings_dir: str) -> None:
    """Stop when idle is idempotent."""
    svc = CameraRecordingService(recordings_dir=recordings_dir)
    state, err = svc.stop_recording()
    assert err is None
    assert state.recording is False


def test_camera_command_missing(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Start returns error when neither rpicam-vid nor libcamera-vid found."""
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.get_camera_video_command",
        lambda: None,
    )
    svc = CameraRecordingService(recordings_dir=recordings_dir)
    state, err = svc.start_recording()
    assert "rpicam-vid or libcamera-vid" in (err or "")
    assert state.recording is False


def test_start_recording_process_dies_immediately(
    monkeypatch: pytest.MonkeyPatch,
    recordings_dir: str,
) -> None:
    """When process exits immediately, return failure with stderr."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # Process died immediately (exited)
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b"camera not found"
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("time.sleep"):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                state, err = svc.start_recording()
    assert err is not None
    assert "camera not found" in err or "Process exited" in err
    assert state.recording is False


def test_is_available_rpicam_vid(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """is_available True when rpicam-vid exists."""
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.get_camera_video_command",
        lambda: "rpicam-vid",
    )
    svc = CameraRecordingService(recordings_dir=recordings_dir)
    assert svc.is_available() is True


def test_is_available_libcamera_vid(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """is_available True when libcamera-vid exists."""
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.get_camera_video_command",
        lambda: "libcamera-vid",
    )
    svc = CameraRecordingService(recordings_dir=recordings_dir)
    assert svc.is_available() is True


def test_is_available_neither(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """is_available False when neither command exists."""
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.get_camera_video_command",
        lambda: None,
    )
    svc = CameraRecordingService(recordings_dir=recordings_dir)
    assert svc.is_available() is False


def test_start_recording_uses_rpicam_vid_mp4(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When rpicam-vid is used, output is .mp4 and Popen gets rpicam-vid."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ) as mock_popen:
            with patch("time.sleep"):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                state, err = svc.start_recording()
    assert err is None
    assert state.recording is True
    assert state.output_file is not None
    assert state.output_file.endswith(".mp4")
    call_args = mock_popen.call_args[0][0]
    assert call_args[0] == "rpicam-vid"


def test_start_recording_logs_command(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Recording start logs which command is used."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("airautomatica.services.camera_recording.logger") as mock_logger:
                with patch("time.sleep"):
                    svc = CameraRecordingService(recordings_dir=recordings_dir)
                    svc.start_recording()
    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args[0]
    assert "Recording started" in str(call_args) and "rpicam-vid" in str(call_args)


def test_manual_mode_does_not_auto_start(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """In manual mode, armed transition does not trigger start."""
    monkeypatch.setenv("CAMERA_RECORDING_MODE", "manual")
    from airautomatica.settings import load_settings

    load_settings()
    from airautomatica.config import get_camera_recording_mode

    svc = CameraRecordingService(recordings_dir=recordings_dir)
    ctrl = RecordingAutoController(svc, get_camera_recording_mode)
    state_armed = AircraftState(
        connected=True,
        heartbeat=1,
        mode="GUIDED",
        armed=True,
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
        timestamp=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )
    ctrl.maybe_auto_record(state_armed)
    assert svc.get_recording_state().recording is False


def test_auto_mode_starts_on_armed(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """In auto mode, armed False->True triggers start."""
    monkeypatch.setenv("CAMERA_RECORDING_MODE", "auto")
    from airautomatica.settings import load_settings

    load_settings()
    from airautomatica.config import get_camera_recording_mode

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("time.sleep"):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                ctrl = RecordingAutoController(svc, get_camera_recording_mode)
                from datetime import datetime, timezone

                state_armed = AircraftState(
                    connected=True,
                    heartbeat=1,
                    mode="GUIDED",
                    armed=True,
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
                ctrl.maybe_auto_record(state_armed)
    assert svc.get_recording_state().recording is True


def test_auto_mode_stops_on_disarmed(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """In auto mode, armed True->False triggers stop."""
    monkeypatch.setenv("CAMERA_RECORDING_MODE", "auto")
    from airautomatica.settings import load_settings

    load_settings()
    from airautomatica.config import get_camera_recording_mode

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("time.sleep"):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                ctrl = RecordingAutoController(svc, get_camera_recording_mode)
                from datetime import datetime, timezone

                state_armed = AircraftState(
                    connected=True,
                    heartbeat=1,
                    mode="GUIDED",
                    armed=True,
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
                state_disarmed = AircraftState(
                    connected=True,
                    heartbeat=2,
                    mode="GUIDED",
                    armed=False,
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
                ctrl.maybe_auto_record(state_armed)
                ctrl.maybe_auto_record(state_disarmed)
    assert svc.get_recording_state().recording is False


def test_auto_mode_no_duplicate_starts(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """In auto mode, armed stays True does not restart."""
    monkeypatch.setenv("CAMERA_RECORDING_MODE", "auto")
    from airautomatica.settings import load_settings

    load_settings()
    from airautomatica.config import get_camera_recording_mode

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ) as mock_popen:
            with patch("time.sleep"):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                ctrl = RecordingAutoController(svc, get_camera_recording_mode)
                from datetime import datetime, timezone

                state = AircraftState(
                    connected=True,
                    heartbeat=1,
                    mode="GUIDED",
                    armed=True,
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
                ctrl.maybe_auto_record(state)
                ctrl.maybe_auto_record(state)
                ctrl.maybe_auto_record(state)
    assert mock_popen.call_count == 1
