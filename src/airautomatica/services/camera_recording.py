"""Camera recording service using rpicam-vid (modern Pi OS) or libcamera-vid (legacy). Supports manual and auto (armed-based) recording."""

import logging
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from airautomatica.config import get_recordings_dir

if TYPE_CHECKING:
    from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)

_CAMERA_VID_COMMANDS = ("rpicam-vid", "libcamera-vid")
MAV_MODE_FLAG_ARMED = 128
_TERMINATE_WAIT_SEC = 2.5
_LIVENESS_POLL_SEC = 0.2


def get_camera_video_command() -> Optional[str]:
    """Return first available camera video command, or None. Prefers rpicam-vid (modern Pi OS)."""
    for cmd in _CAMERA_VID_COMMANDS:
        if shutil.which(cmd) is not None:
            return cmd
    return None


@dataclass
class RecordingState:
    """Recording state only. No error fields."""

    recording: bool
    output_file: Optional[str]  # basename for health/API
    started_at: Optional[datetime]
    last_recorded_file: Optional[
        str
    ]  # basename of last completed recording (when not recording)


class CameraRecordingService:
    """Manages rpicam-vid or libcamera-vid subprocess for video recording."""

    def __init__(self, recordings_dir: Optional[str] = None) -> None:
        self._recordings_dir = Path(recordings_dir or get_recordings_dir())
        self._lock = threading.Lock()
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._output_path: Optional[Path] = None
        self._started_at: Optional[datetime] = None
        self._last_recorded_file: Optional[str] = None
        self._last_error: Optional[str] = None

    @property
    def recordings_dir(self) -> str:
        """Path to recordings directory."""
        return str(self._recordings_dir)

    def get_recording_state(self) -> RecordingState:
        """Return current recording state."""
        with self._lock:
            is_alive = self._process is not None and self._process.poll() is None
            if self._process is not None and not is_alive:
                exit_code = self._process.returncode
                stderr = b""
                if self._process.stderr:
                    try:
                        _, stderr = self._process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait()
                        stderr = (
                            self._process.stderr.read() if self._process.stderr else b""
                        )
                stderr = stderr or b""
                err = stderr.decode("utf-8", errors="replace").strip() or "no stderr"
                self._last_error = f"exit_code={exit_code}: {err}"
                logger.warning(
                    "Recording process exited unexpectedly (exit_code=%s): %s",
                    exit_code,
                    err,
                )
                self._process = None
                self._output_path = None
            basename = self._output_path.name if self._output_path else None
            return RecordingState(
                recording=is_alive,
                output_file=basename,
                started_at=self._started_at,
                last_recorded_file=self._last_recorded_file,
            )

    def is_available(self) -> bool:
        """True if rpicam-vid or libcamera-vid is present and service is usable."""
        return get_camera_video_command() is not None

    def start_recording(self) -> tuple[RecordingState, Optional[str]]:
        """Start recording. Returns (state, error_message). Error is None on success."""
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                basename = self._output_path.name if self._output_path else None
                return (
                    RecordingState(
                        recording=True,
                        output_file=basename,
                        started_at=self._started_at,
                        last_recorded_file=self._last_recorded_file,
                    ),
                    None,
                )
            logger.info("Recording start requested")
            cmd = get_camera_video_command()
            if cmd is None:
                self._last_error = "rpicam-vid or libcamera-vid not found"
                return (
                    RecordingState(
                        recording=False,
                        output_file=None,
                        started_at=None,
                        last_recorded_file=self._last_recorded_file,
                    ),
                    "rpicam-vid or libcamera-vid not found",
                )
            self._recordings_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
            ext = "mp4" if cmd == "rpicam-vid" else "h264"
            self._output_path = self._recordings_dir / f"{ts}_cam.{ext}"
            args = [cmd, "-t", "0"]
            if cmd == "rpicam-vid":
                args.extend(["--codec", "libav"])
            args.extend(["-o", str(self._output_path)])
            try:
                self._process = subprocess.Popen(args, stderr=subprocess.PIPE)
                logger.info("Recording command launched: %s", " ".join(args))
            except Exception as e:
                self._last_error = str(e)
                logger.warning("Recording start failed: %s", e)
                return (
                    RecordingState(
                        recording=False,
                        output_file=None,
                        started_at=None,
                        last_recorded_file=self._last_recorded_file,
                    ),
                    str(e),
                )
            time.sleep(_LIVENESS_POLL_SEC)
            if self._process.poll() is not None:
                exit_code = self._process.returncode
                stderr = b""
                if self._process.stderr:
                    try:
                        _, stderr = self._process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait()
                        stderr = (
                            self._process.stderr.read() if self._process.stderr else b""
                        )
                stderr = stderr or b""
                err = (
                    stderr.decode("utf-8", errors="replace").strip() or "Process exited"
                )
                err_msg = f"exit_code={exit_code}: {err}"
                self._last_error = err_msg
                self._process = None
                self._output_path = None
                logger.warning(
                    "Recording process exited early (exit_code=%s): %s", exit_code, err
                )
                return (
                    RecordingState(
                        recording=False,
                        output_file=None,
                        started_at=None,
                        last_recorded_file=self._last_recorded_file,
                    ),
                    err_msg,
                )
            self._started_at = datetime.now(timezone.utc)
            self._last_error = None
            basename = self._output_path.name
            logger.info("Recording started (%s): %s", cmd, basename)
            return (
                RecordingState(
                    recording=True,
                    output_file=basename,
                    started_at=self._started_at,
                    last_recorded_file=self._last_recorded_file,
                ),
                None,
            )

    def stop_recording(self) -> tuple[RecordingState, Optional[str]]:
        """Stop recording. Returns (state, error_message). Error is None on success."""
        with self._lock:
            basename = self._output_path.name if self._output_path else None
            if self._process is None or self._process.poll() is not None:
                self._process = None
                self._output_path = None
                self._started_at = None
                return (
                    RecordingState(
                        recording=False,
                        output_file=None,
                        started_at=None,
                        last_recorded_file=self._last_recorded_file,
                    ),
                    None,
                )
            self._process.terminate()
            try:
                self._process.wait(timeout=_TERMINATE_WAIT_SEC)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            if basename:
                self._last_recorded_file = basename
                logger.info("Recording stopped: %s", basename)
            self._process = None
            self._output_path = None
            self._started_at = None
            return (
                RecordingState(
                    recording=False,
                    output_file=None,
                    started_at=None,
                    last_recorded_file=self._last_recorded_file,
                ),
                None,
            )

    def stop_and_cleanup(self) -> None:
        """Terminate active recording on app shutdown."""
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                return
            self._process.terminate()
            try:
                self._process.wait(timeout=_TERMINATE_WAIT_SEC)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None
            self._output_path = None
            self._started_at = None


class RecordingAutoController:
    """Edge-triggered auto recording based on armed state."""

    def __init__(
        self,
        service: CameraRecordingService,
        get_mode_fn: Callable[[], str],
    ) -> None:
        self._service = service
        self._get_mode = get_mode_fn
        self._last_armed: Optional[bool] = None

    def maybe_auto_record(self, state: "AircraftState") -> None:
        """Call from telemetry loop. Start/stop based on armed transitions in auto mode."""
        mode = self._get_mode()
        if mode != "auto":
            return
        armed = state.armed
        rec_state = self._service.get_recording_state()
        if (
            armed
            and (self._last_armed is None or not self._last_armed)
            and not rec_state.recording
        ):
            new_state, err = self._service.start_recording()
            if err is None and new_state.output_file:
                logger.info("Auto recording started (armed): %s", new_state.output_file)
            elif err:
                logger.warning("Auto recording start failed: %s", err)
        elif not armed and self._last_armed and rec_state.recording:
            logger.info(
                "Auto-stop triggered: armed=False, last_armed=True, stopping %s",
                rec_state.output_file or "recording",
            )
            _, _ = self._service.stop_recording()
        self._last_armed = armed
