"""Tests for camera recording service and auto controller."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from airautomatica.models.state import AircraftState
from airautomatica.services.camera_recording import (
    CameraRecordingService,
    RecordingAutoController,
)

_FILENAME_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d{6})_cam\.(mp4|h264)$", re.IGNORECASE
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


def test_get_recording_state_detects_unexpected_exit(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When process exits unexpectedly after start, get_recording_state detects and cleans up."""
    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, 1]
    mock_proc.returncode = 1
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b"camera disconnected"
    mock_proc.communicate.return_value = (None, b"camera disconnected")
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
                state1, err = svc.start_recording()
    assert err is None
    assert state1.recording is True
    state2 = svc.get_recording_state()
    assert state2.recording is False
    assert svc._last_error is not None
    assert "camera disconnected" in svc._last_error


def test_start_recording_process_dies_immediately(
    monkeypatch: pytest.MonkeyPatch,
    recordings_dir: str,
) -> None:
    """When process exits immediately, return failure with stderr."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # Process died immediately (exited)
    mock_proc.returncode = 1
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b"camera not found"
    mock_proc.communicate.return_value = (None, b"camera not found")
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
    """When rpicam-vid is used, output is .mp4. With ffmpeg: pipe path; without: direct -o."""
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
    # First Popen is camera; second (if any) is ffmpeg. Assert on camera args.
    calls = mock_popen.call_args_list
    cam_args = calls[0][0][0]
    assert cam_args[0] == "rpicam-vid"
    assert "-t" in cam_args and "0" in cam_args
    assert "-o" in cam_args


def test_rpicam_vid_uses_mpegts_pipe_when_ffmpeg_available(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When rpicam-vid + ffmpeg: use libav mpegts for proper encapsulation when piping."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.subprocess.Popen",
                return_value=mock_proc,
            ) as mock_popen:
                with patch("time.sleep"):
                    svc = CameraRecordingService(recordings_dir=recordings_dir)
                    svc.start_recording()
    cam_args = mock_popen.call_args_list[0][0][0]
    assert "--codec" in cam_args
    assert "libav" in cam_args
    assert "--libav-format" in cam_args
    assert "mpegts" in cam_args
    assert "--nopreview" in cam_args


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
    info_calls = [str(c) for c in mock_logger.info.call_args_list]
    assert any("Recording started" in c and "rpicam-vid" in c for c in info_calls)


def test_manual_mode_does_not_auto_stop(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """In manual mode, armed->disarmed does not stop an active recording."""
    monkeypatch.setenv("CAMERA_RECORDING_MODE", "manual")
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
                svc.start_recording()
    assert svc.get_recording_state().recording is True
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
        timestamp=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )
    ctrl.maybe_auto_record(state_disarmed)
    assert svc.get_recording_state().recording is True


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


def test_auto_mode_stops_on_disarmed_calls_mark_as_auto_when_session_ref(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """In auto mode with session_ref, auto-stop calls mark_as_auto with basename and session_id."""
    monkeypatch.setenv("CAMERA_RECORDING_MODE", "auto")
    from airautomatica.settings import load_settings

    load_settings()
    from airautomatica.config import get_camera_recording_mode

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    session_ref: list[int | None] = [123]
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
                ctrl = RecordingAutoController(
                    svc,
                    get_camera_recording_mode,
                    debounce_sec=0,
                    session_ref=session_ref,
                )
                with patch.object(svc, "mark_as_auto") as mock_mark:
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
                    output_file = svc.get_recording_state().output_file
                    assert output_file is not None
                    Path(recordings_dir).mkdir(parents=True, exist_ok=True)
                    (Path(recordings_dir) / output_file).write_bytes(b"fake")
                    ctrl.maybe_auto_record(state_disarmed)
                    assert svc.get_recording_state().recording is False
                    mock_mark.assert_called_once()
                    call_args = mock_mark.call_args
                    assert call_args[0][0] == output_file
                    assert call_args[0][1] == 123


def test_auto_mode_stops_on_disarmed(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """In auto mode, armed True->False triggers stop (with debounce_sec=0 for test)."""
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
                ctrl = RecordingAutoController(
                    svc, get_camera_recording_mode, debounce_sec=0
                )
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


def test_auto_mode_ignores_disarm_when_disconnected(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When state.connected=False and armed=False, do not stop recording (hold last armed)."""
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
                ctrl = RecordingAutoController(
                    svc, get_camera_recording_mode, debounce_sec=0
                )
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
                state_disconnected_disarmed = AircraftState(
                    connected=False,
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
                ctrl.maybe_auto_record(state_disconnected_disarmed)
    assert svc.get_recording_state().recording is True


def test_auto_mode_disarm_debounce(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Require armed=False for debounce_sec before stop; armed=True before debounce cancels."""
    import threading

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
            with patch(
                "airautomatica.services.camera_recording.time.sleep",
            ):
                svc = CameraRecordingService(recordings_dir=recordings_dir)
                ctrl = RecordingAutoController(
                    svc, get_camera_recording_mode, debounce_sec=0.02
                )
                from datetime import datetime, timezone

                def make_state(connected: bool, armed: bool) -> AircraftState:
                    return AircraftState(
                        connected=connected,
                        heartbeat=1,
                        mode="GUIDED",
                        armed=armed,
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

                ctrl.maybe_auto_record(make_state(True, True))
                ctrl.maybe_auto_record(make_state(True, False))
                assert svc.get_recording_state().recording is True
                threading.Event().wait(0.03)
                ctrl.maybe_auto_record(make_state(True, False))
                assert svc.get_recording_state().recording is False


def test_auto_mode_startup_while_armed(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """First state with armed=True and _last_armed=None starts recording (intentional)."""
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


# --- Phase 2 regression tests ---


def test_pipe_mode_start_succeeds_and_sets_both_processes(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Pipe mode (rpicam-vid + ffmpeg) leaves both _process and _muxer_process set."""
    mock_cam = MagicMock()
    mock_cam.poll.return_value = None
    mock_cam.stdout = MagicMock()
    mock_muxer = MagicMock()
    mock_muxer.poll.return_value = None

    def fake_popen(args, **kwargs):
        if "mpegts" in str(args) or "-i" in str(args):
            return mock_muxer
        return mock_cam

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.subprocess.Popen",
                side_effect=fake_popen,
            ):
                with patch("time.sleep"):
                    svc = CameraRecordingService(recordings_dir=recordings_dir)
                    state, err = svc.start_recording()
    assert err is None
    assert state.recording is True
    assert svc._process is not None
    assert svc._muxer_process is not None


def test_direct_mode_start_succeeds_and_leaves_muxer_unset(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Direct mode (libcamera-vid or rpicam-vid without ffmpeg) leaves _muxer_process None."""
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
    assert svc._process is not None
    assert svc._muxer_process is None


def test_muxer_exits_immediately_after_launch(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When muxer exits immediately after launch, return failure and clean up both handles."""
    mock_cam = MagicMock()
    mock_cam.poll.return_value = None
    mock_cam.stdout = MagicMock()
    mock_muxer = MagicMock()
    mock_muxer.poll.return_value = 1
    mock_muxer.returncode = 1
    mock_muxer.stderr = MagicMock()
    mock_muxer.stderr.read.return_value = b"muxer failed"

    def fake_popen(args, **kwargs):
        if "mpegts" in str(args) or "-i" in str(args):
            return mock_muxer
        return mock_cam

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.subprocess.Popen",
                side_effect=fake_popen,
            ):
                with patch("time.sleep"):
                    svc = CameraRecordingService(recordings_dir=recordings_dir)
                    state, err = svc.start_recording()
    assert err is not None
    assert "muxer" in err.lower() or "exit" in err.lower()
    assert state.recording is False
    assert svc._process is None
    assert svc._muxer_process is None


def test_partial_startup_failure_popen_raises_on_second_call(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Partial startup (a): second Popen raises after first process launched; both refs cleared."""
    call_count = 0

    def failing_popen(args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("ffmpeg not found")
        return MagicMock(poll=lambda: None, stdout=MagicMock(), stderr=MagicMock())

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.subprocess.Popen",
                side_effect=failing_popen,
            ):
                with patch("time.sleep"):
                    svc = CameraRecordingService(recordings_dir=recordings_dir)
                    state, err = svc.start_recording()
    assert err is not None
    assert state.recording is False
    assert svc._process is None
    assert svc._muxer_process is None


def test_partial_startup_failure_muxer_unhealthy_immediately(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Partial startup (b): first launched, second exists but unhealthy immediately; both refs cleared."""
    mock_cam = MagicMock()
    mock_cam.poll.return_value = None
    mock_cam.stdout = MagicMock()
    mock_muxer = MagicMock()
    mock_muxer.poll.return_value = 1
    mock_muxer.returncode = 1
    mock_muxer.stderr = MagicMock()
    mock_muxer.stderr.read.return_value = b"muxer failed"

    def fake_popen(args, **kwargs):
        if "mpegts" in str(args) or "-i" in str(args):
            return mock_muxer
        return mock_cam

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.subprocess.Popen",
                side_effect=fake_popen,
            ):
                with patch("time.sleep"):
                    svc = CameraRecordingService(recordings_dir=recordings_dir)
                    state, err = svc.start_recording()
    assert err is not None
    assert "muxer" in err.lower() or "exit" in err.lower()
    assert state.recording is False
    assert svc._process is None
    assert svc._muxer_process is None


def test_output_path_filename_creation_unchanged(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Output path uses YYYY-MM-DD_HHMMSS_cam.ext format."""
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
    assert state.output_file is not None
    assert _FILENAME_PATTERN.match(
        state.output_file
    ), f"Bad filename: {state.output_file}"
    assert state.output_file.endswith("_cam.h264")
    assert svc._output_path is not None
    assert str(svc._output_path).endswith("_cam.h264")


def test_overlay_enabled_affects_command_construction(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When overlay enabled and assets exist, command includes overlay args."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    monkeypatch.setenv("AI_HAT_ENABLED", "1")
    monkeypatch.setenv("RECORDING_AI_OVERLAY_ENABLED", "1")
    from airautomatica.settings import load_settings

    load_settings()

    class FakeAssetsPath:
        def exists(self) -> bool:
            return True

        def __str__(self) -> str:
            return "/nonexistent/hailo_yolov6.json"

    fake_assets = FakeAssetsPath()

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.RPCAM_ASSETS_PATH",
            fake_assets,
        ):
            with patch(
                "airautomatica.services.camera_recording.subprocess.Popen",
                return_value=mock_proc,
            ) as mock_popen:
                with patch("time.sleep"):
                    svc = CameraRecordingService(recordings_dir=recordings_dir)
                    svc.start_recording()
    cam_args = mock_popen.call_args_list[0][0][0]
    assert "--post-process-file" in cam_args
    assert "--width" in cam_args and "1280" in cam_args


def test_ingest_startup_only_on_successful_recording(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Ingest is not started when recording start fails."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b"camera error"
    mock_persistence = MagicMock()

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("time.sleep"):
                svc = CameraRecordingService(
                    recordings_dir=recordings_dir,
                    session_ref=[1],
                    persistence=mock_persistence,
                )
                with patch(
                    "airautomatica.services.camera_recording.get_recording_ai_persist_enabled",
                    return_value=True,
                ):
                    state, err = svc.start_recording()
    assert err is not None
    assert state.recording is False
    assert svc._ingest is None


def test_ingest_not_created_when_session_none(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When persist enabled but session is None, ingest is not created (fail fast)."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b""
    mock_persistence = MagicMock()

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("time.sleep"):
                svc = CameraRecordingService(
                    recordings_dir=recordings_dir,
                    session_ref=[None],
                    persistence=mock_persistence,
                )
                with patch(
                    "airautomatica.services.camera_recording.get_recording_ai_persist_enabled",
                    return_value=True,
                ):
                    state, err = svc.start_recording()
    assert err is None
    assert state.recording is True
    assert svc._ingest is None


def test_ingest_not_created_when_overlay_enabled(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When overlay and persist both enabled, ingest is not created (Hailo device contention)."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b""
    mock_persistence = MagicMock()

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="libcamera-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.subprocess.Popen",
            return_value=mock_proc,
        ):
            with patch("time.sleep"):
                svc = CameraRecordingService(
                    recordings_dir=recordings_dir,
                    session_ref=[42],
                    persistence=mock_persistence,
                )
                with patch(
                    "airautomatica.services.camera_recording.get_recording_ai_persist_enabled",
                    return_value=True,
                ):
                    with patch(
                        "airautomatica.services.camera_recording.get_recording_ai_overlay_enabled",
                        return_value=True,
                    ):
                        state, err = svc.start_recording()
    assert err is None
    assert state.recording is True
    assert svc._ingest is None


def test_stop_after_failed_or_partial_start_does_not_explode(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """Stop when start failed or partial is idempotent and does not raise."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b"died"
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


def test_reconcile_dead_process_stable_once_updated(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """When process is already dead, get_recording_state updates internal state once; subsequent calls are stable."""
    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, 1, 1]
    mock_proc.returncode = 1
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b"camera disconnected"
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
    state1 = svc.get_recording_state()
    state2 = svc.get_recording_state()
    assert state1.recording is False
    assert state2.recording is False
    assert svc._process is None
    assert svc._last_error is not None


def test_started_at_not_set_on_any_failure_path(
    monkeypatch: pytest.MonkeyPatch, recordings_dir: str
) -> None:
    """_started_at remains None across all failure paths."""
    # Precondition failure: cmd missing
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.get_camera_video_command",
        lambda: None,
    )
    svc = CameraRecordingService(recordings_dir=recordings_dir)
    svc.start_recording()
    assert svc._started_at is None

    # Popen raises on second call (pipe mode)
    call_count = 0

    def failing_popen(args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("ffmpeg not found")
        return MagicMock(poll=lambda: None, stdout=MagicMock(), stderr=MagicMock())

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.subprocess.Popen",
                side_effect=failing_popen,
            ):
                with patch("time.sleep"):
                    svc2 = CameraRecordingService(recordings_dir=recordings_dir)
                    svc2.start_recording()
    assert svc2._started_at is None

    # Camera exits immediately
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1
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
                svc3 = CameraRecordingService(recordings_dir=recordings_dir)
                svc3.start_recording()
    assert svc3._started_at is None

    # Muxer exits immediately
    mock_cam = MagicMock()
    mock_cam.poll.return_value = None
    mock_cam.stdout = MagicMock()
    mock_muxer = MagicMock()
    mock_muxer.poll.return_value = 1
    mock_muxer.returncode = 1
    mock_muxer.stderr = MagicMock()
    mock_muxer.stderr.read.return_value = b"muxer failed"

    def fake_popen(args, **kwargs):
        if "mpegts" in str(args) or "-i" in str(args):
            return mock_muxer
        return mock_cam

    with patch(
        "airautomatica.services.camera_recording.get_camera_video_command",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_recording.get_ffmpeg_command",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "airautomatica.services.camera_recording.subprocess.Popen",
                side_effect=fake_popen,
            ):
                with patch("time.sleep"):
                    svc4 = CameraRecordingService(recordings_dir=recordings_dir)
                    svc4.start_recording()
    assert svc4._started_at is None
