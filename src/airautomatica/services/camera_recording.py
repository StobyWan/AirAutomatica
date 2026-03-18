"""Camera recording service using rpicam-vid (modern Pi OS) or libcamera-vid (legacy). Supports manual and auto (armed-based) recording."""

import json
import logging
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterator, List, Optional

from airautomatica.ai.hailo_detection import RPCAM_ASSETS_PATH
from airautomatica.camera.backends.csi import csi_camera_index_args
from airautomatica.camera.backends.usb import usb_recording_argv
from airautomatica.camera.selector import CameraSelector
from airautomatica.config import (
    get_camera_recording_disarm_debounce_sec,
    get_recording_ai_overlay_enabled,
    get_recording_ai_persist_enabled,
    get_recording_telemetry_overlay_enabled,
    get_recordings_dir,
)
from airautomatica.services.camera_preview import release_camera_for_recording
from airautomatica.services.recording_ai_ingest import RecordingAiIngest
from airautomatica.services.recordings_service import (
    _FILENAME_PATTERN,
    _meta_path_for_recording,
)
from airautomatica.services.telemetry_overlay import TelemetryWriter

if TYPE_CHECKING:
    from airautomatica.models.state import AircraftState
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)

_CAMERA_VID_COMMANDS = ("rpicam-vid", "libcamera-vid")
_FFMPEG_COMMAND = "ffmpeg"
MAV_MODE_FLAG_ARMED = 128
_TERMINATE_WAIT_SEC = (
    8.0  # Allow time for rpicam-vid to finalize MP4 moov atom on SIGTERM
)
_LIVENESS_POLL_SEC = 0.2
_MUXER_WAIT_SEC = 8.0
_JPEG_SOI = b"\xff\xd8\xff"
_JPEG_EOI = b"\xff\xd9"
_RECORDING_STREAM_BOUNDARY = b"frame"
_RECORDING_STREAM_QUEUE_MAX = 2
_RECORDING_STREAM_SENTINEL = object()


def get_camera_video_command() -> Optional[str]:
    """Return first available camera video command, or None. Prefers rpicam-vid (modern Pi OS)."""
    for cmd in _CAMERA_VID_COMMANDS:
        if shutil.which(cmd) is not None:
            return cmd
    return None


def get_ffmpeg_command() -> Optional[str]:
    """Return ffmpeg path if available."""
    return shutil.which(_FFMPEG_COMMAND)


def _read_process_stderr(proc: subprocess.Popen[bytes]) -> str:
    """Best-effort stderr read without touching stdout pipes."""
    if proc.stderr is None:
        return ""
    try:
        data = proc.stderr.read()
    except Exception:
        return ""
    return data.decode("utf-8", errors="replace").strip()


def _wait_and_terminate(
    proc: Optional[subprocess.Popen[bytes]], timeout: float
) -> None:
    """Wait for process; terminate if still alive; kill if terminate times out.
    Caller sets process reference to None after."""
    if proc is None:
        return
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _overlay_args_if_enabled(cmd: str) -> list[str]:
    """Return rpicam-vid overlay args when enabled, else []."""
    if (
        cmd != "rpicam-vid"
        or not get_recording_ai_overlay_enabled()
        or not RPCAM_ASSETS_PATH.exists()
    ):
        return []
    logger.info("Recording AI overlay enabled (Hailo post-process)")
    return [
        "--width",
        "1280",
        "--height",
        "720",
        "--post-process-file",
        str(RPCAM_ASSETS_PATH),
        "--lores-width",
        "640",
        "--lores-height",
        "640",
    ]


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

    def __init__(
        self,
        recordings_dir: Optional[str] = None,
        session_ref: Optional[List[Optional[int]]] = None,
        persistence: Optional["PersistenceService"] = None,
        get_state: Optional[Callable[[], "AircraftState | None"]] = None,
    ) -> None:
        self._recordings_dir = Path(recordings_dir or get_recordings_dir()).resolve()
        self._lock = threading.Lock()
        self._session_ref = session_ref
        self._persistence = persistence
        self._get_state = get_state
        self._ingest: Optional[RecordingAiIngest] = None
        cam_cmd = get_camera_video_command()
        ffmpeg_cmd = get_ffmpeg_command()
        # Strategy: rpicam-vid + ffmpeg -> pipe (MPEG-TS to MP4); else direct file output
        strategy = (
            "pipe" if (cam_cmd == "rpicam-vid" and ffmpeg_cmd is not None) else "direct"
        )
        logger.info(
            "AIRAUTOMATICA camera_recording: __file__=%s cam=%s ffmpeg=%s strategy=%s dir=%s",
            __file__,
            cam_cmd or "none",
            ffmpeg_cmd or "none",
            strategy,
            self._recordings_dir,
        )
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._muxer_process: Optional[subprocess.Popen[bytes]] = None
        self._output_path: Optional[Path] = None
        self._started_at: Optional[datetime] = None
        self._last_recorded_file: Optional[str] = None
        self._last_error: Optional[str] = None
        self._telemetry_writer: Optional[TelemetryWriter] = None
        self._recording_stream_queue: Optional[queue.Queue[object]] = None
        self._recording_stream_thread: Optional[threading.Thread] = None

    @property
    def recordings_dir(self) -> str:
        """Path to recordings directory."""
        return str(self._recordings_dir)

    def _idle_state(self) -> RecordingState:
        """Return RecordingState for idle (not recording)."""
        return RecordingState(
            recording=False,
            output_file=None,
            started_at=None,
            last_recorded_file=self._last_recorded_file,
        )

    def _stop_telemetry_writer(self) -> None:
        """Stop telemetry overlay writer and remove temp file. Idempotent."""
        if self._telemetry_writer is not None:
            try:
                self._telemetry_writer.stop()
            except Exception as e:
                logger.warning("Telemetry writer stop failed: %s", e)
            self._telemetry_writer = None

    def _stop_recording_stream(self) -> None:
        """Stop recording stream drain thread and signal consumers. Idempotent."""
        if self._recording_stream_queue is not None:
            q = self._recording_stream_queue
            self._recording_stream_queue = None
            try:
                while q.full():
                    q.get_nowait()
                q.put_nowait(_RECORDING_STREAM_SENTINEL)
            except Exception:
                pass
        if self._recording_stream_thread is not None:
            self._recording_stream_thread.join(timeout=2.0)
            self._recording_stream_thread = None

    def _drain_recording_stream(self) -> None:
        """Read MJPEG from ffmpeg stdout, parse JPEG frames, put in queue. Runs in thread."""
        if self._muxer_process is None or self._muxer_process.stdout is None:
            return
        pipe = self._muxer_process.stdout
        buf = b""
        q = self._recording_stream_queue
        try:
            while q is not None:
                chunk = pipe.read(8192) if pipe else b""
                if not chunk:
                    break
                buf += chunk
                while True:
                    soi = buf.find(_JPEG_SOI)
                    if soi < 0:
                        break
                    eoi = buf.find(_JPEG_EOI, soi)
                    if eoi <= soi:
                        break
                    frame = buf[soi : eoi + 2]
                    buf = buf[eoi + 2 :]
                    try:
                        if q.full():
                            q.get_nowait()
                        q.put_nowait(frame)
                    except queue.Full:
                        try:
                            q.get_nowait()
                            q.put_nowait(frame)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("Recording stream drain stopped: %s", e)
        finally:
            if q is not None:
                try:
                    q.put(_RECORDING_STREAM_SENTINEL)
                except Exception:
                    pass

    def get_recording_stream(self) -> Optional[Iterator[bytes]]:
        """Yield multipart MJPEG chunks when recording with overlay. None when unavailable."""
        if self._recording_stream_queue is None:
            return None
        if self._process is None or self._process.poll() is not None:
            return None
        if self._muxer_process is None or self._muxer_process.poll() is not None:
            return None

        def _generate() -> Iterator[bytes]:
            q = self._recording_stream_queue
            if q is None:
                return
            try:
                while True:
                    item = q.get(timeout=30.0)
                    if item is _RECORDING_STREAM_SENTINEL:
                        break
                    if isinstance(item, bytes):
                        yield (
                            b"--"
                            + _RECORDING_STREAM_BOUNDARY
                            + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(item)).encode()
                            + b"\r\n\r\n"
                            + item
                            + b"\r\n"
                        )
            except queue.Empty:
                pass
            except Exception as e:
                logger.debug("Recording stream consumer stopped: %s", e)

        return _generate()

    def _reconcile_dead_processes(self) -> None:
        """Idempotent: detect and clean up dead cam/muxer processes. Call once at start of get_recording_state."""
        if self._muxer_process is not None and self._muxer_process.poll() is not None:
            mux_exit = self._muxer_process.returncode
            mux_err = _read_process_stderr(self._muxer_process) or "no stderr"
            logger.warning(
                "Recording muxer exited unexpectedly pid=%s exit_code=%s: %s",
                self._muxer_process.pid,
                mux_exit,
                mux_err,
            )
            self._last_error = f"muxer_exit_code={mux_exit}: {mux_err}"
            self._stop_telemetry_writer()
            self._stop_recording_stream()
            if self._process is not None and self._process.poll() is None:
                _wait_and_terminate(self._process, _TERMINATE_WAIT_SEC)
                self._process = None
            self._muxer_process = None
            self._output_path = None
            self._started_at = None

        if self._process is not None and self._process.poll() is not None:
            pid = self._process.pid
            exit_code = self._process.returncode
            err = _read_process_stderr(self._process) or "no stderr"
            self._last_error = f"exit_code={exit_code}: {err}"
            logger.warning(
                "Recording process exited unexpectedly pid=%s exit_code=%s: %s",
                pid,
                exit_code,
                err,
            )
            self._stop_telemetry_writer()
            self._stop_recording_stream()
            if self._muxer_process is not None:
                _wait_and_terminate(self._muxer_process, _MUXER_WAIT_SEC)
                self._muxer_process = None
            self._process = None
            self._output_path = None
            self._started_at = None

    def mark_as_auto(self, basename: str, session_id: int) -> None:
        """Write sidecar .meta marking this recording as auto-triggered for the given session."""
        if not basename or not _FILENAME_PATTERN.match(basename):
            logger.debug("mark_as_auto: invalid basename %r", basename)
            return
        path = self._recordings_dir / basename
        meta_path = _meta_path_for_recording(path)
        try:
            meta_path.write_text(
                json.dumps({"trigger": "auto", "session_id": session_id}),
                encoding="utf-8",
            )
            logger.debug("mark_as_auto: wrote %s", meta_path)
        except OSError as e:
            logger.warning("mark_as_auto failed for %s: %s", basename, e)

    def get_recording_state(self) -> RecordingState:
        """Return current recording state."""
        with self._lock:
            self._reconcile_dead_processes()
            is_alive = self._process is not None and self._process.poll() is None
            basename = self._output_path.name if self._output_path else None
            return RecordingState(
                recording=is_alive,
                output_file=basename,
                started_at=self._started_at,
                last_recorded_file=self._last_recorded_file,
            )

    def is_available(self) -> bool:
        """True if rpicam-vid, libcamera-vid, or ffmpeg (for USB) is present."""
        return (
            get_camera_video_command() is not None or get_ffmpeg_command() is not None
        )

    def start_recording(self) -> tuple[RecordingState, Optional[str]]:
        """Start recording. Returns (state, error_message). Error is None on success."""
        with self._lock:
            # 1. Validate preconditions
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
            descriptor = CameraSelector().resolve()

            self._recordings_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

            release_camera_for_recording()

            usb_output = self._recordings_dir / f"{ts}_cam.mp4"
            usb_argv = (
                usb_recording_argv(descriptor, usb_output) if descriptor else None
            )
            cmd: Optional[str] = None
            if usb_argv:
                self._output_path = usb_output
                logger.info(
                    "Recording output path (absolute): %s",
                    str(self._output_path.resolve()),
                )
                try:
                    self._process = subprocess.Popen(
                        usb_argv,
                        stderr=subprocess.PIPE,
                    )
                    self._muxer_process = None
                    logger.info(
                        "Recording command launched pid=%s (USB): %s",
                        self._process.pid,
                        " ".join(usb_argv),
                    )
                except Exception as e:
                    self._last_error = str(e)
                    logger.warning("USB recording start failed: %s", e)
                    self._process = None
                    self._output_path = None
                    return (self._idle_state(), str(e))
                cmd = "usb"
            else:
                cmd = get_camera_video_command()
                if cmd is None:
                    self._last_error = "rpicam-vid or libcamera-vid not found"
                    return (
                        self._idle_state(),
                        "rpicam-vid or libcamera-vid not found",
                    )
                ext = "mp4" if cmd == "rpicam-vid" else "h264"
                self._output_path = self._recordings_dir / f"{ts}_cam.{ext}"
                logger.info(
                    "Recording output path (absolute): %s",
                    str(self._output_path.resolve()),
                )
                camera_index_args = csi_camera_index_args(descriptor)
                ffmpeg_cmd = get_ffmpeg_command() if cmd == "rpicam-vid" else None
                use_pipe = ffmpeg_cmd is not None and cmd == "rpicam-vid"
                logger.info(
                    "AIRAUTOMATICA camera_recording: strategy=%s (cam=%s ffmpeg=%s)",
                    "pipe" if use_pipe else "direct",
                    cmd,
                    ffmpeg_cmd or "none",
                )
                try:
                    if ffmpeg_cmd is not None:
                        cam_args = (
                            [cmd]
                            + camera_index_args
                            + [
                                "-t",
                                "0",
                                "--nopreview",
                            ]
                        )
                        cam_args.extend(_overlay_args_if_enabled(cmd))
                        cam_args.extend(
                            [
                                "--codec",
                                "libav",
                                "--libav-format",
                                "mpegts",
                                "-o",
                                "-",
                            ]
                        )
                        self._process = subprocess.Popen(
                            cam_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        use_telemetry_overlay = (
                            get_recording_telemetry_overlay_enabled()
                            and self._get_state is not None
                        )
                        if use_telemetry_overlay and self._get_state is not None:
                            get_state_fn = self._get_state
                            self._telemetry_writer = TelemetryWriter(
                                get_state=get_state_fn
                            )
                            telemetry_path = self._telemetry_writer.start()
                            drawtext_filter = (
                                f"drawtext=textfile={telemetry_path}:reload=1:"
                                "fontsize=20:fontcolor=white:borderw=2:bordercolor=black:"
                                "x=10:y=10"
                            )
                            ffmpeg_args = [
                                ffmpeg_cmd,
                                "-hide_banner",
                                "-loglevel",
                                "error",
                                "-y",
                                "-f",
                                "mpegts",
                                "-i",
                                "pipe:0",
                                "-vf",
                                drawtext_filter,
                                "-map",
                                "0:v",
                                "-c:v",
                                "libx264",
                                "-preset",
                                "veryfast",
                                "-movflags",
                                "frag_keyframe+empty_moov+default_base_moof",
                                str(self._output_path),
                                "-map",
                                "0:v",
                                "-c:v",
                                "mjpeg",
                                "-q:v",
                                "5",
                                "-f",
                                "mjpeg",
                                "pipe:1",
                            ]
                        else:
                            ffmpeg_args = [
                                ffmpeg_cmd,
                                "-hide_banner",
                                "-loglevel",
                                "error",
                                "-y",
                                "-f",
                                "mpegts",
                                "-i",
                                "pipe:0",
                                "-c",
                                "copy",
                                "-movflags",
                                "frag_keyframe+empty_moov+default_base_moof",
                                str(self._output_path),
                            ]
                        muxer_stdout = (
                            subprocess.PIPE
                            if use_telemetry_overlay and self._get_state is not None
                            else subprocess.DEVNULL
                        )
                        self._muxer_process = subprocess.Popen(
                            ffmpeg_args,
                            stdin=self._process.stdout,
                            stdout=muxer_stdout,
                            stderr=subprocess.PIPE,
                        )
                        if self._process.stdout:
                            self._process.stdout.close()
                        if (
                            muxer_stdout == subprocess.PIPE
                            and self._muxer_process.stdout is not None
                        ):
                            self._recording_stream_queue = queue.Queue(
                                maxsize=_RECORDING_STREAM_QUEUE_MAX
                            )
                            self._recording_stream_thread = threading.Thread(
                                target=self._drain_recording_stream,
                                daemon=True,
                            )
                            self._recording_stream_thread.start()
                        logger.info(
                            "Recording command launched pid=%s: %s",
                            self._process.pid,
                            " ".join(cam_args),
                        )
                        logger.info(
                            "Recording muxer launched pid=%s: %s",
                            self._muxer_process.pid,
                            " ".join(ffmpeg_args),
                        )
                    else:
                        args = [cmd] + camera_index_args + ["-t", "0"]
                        args.extend(_overlay_args_if_enabled(cmd))
                        args.extend(["-o", str(self._output_path)])
                        self._process = subprocess.Popen(args, stderr=subprocess.PIPE)
                        self._muxer_process = None
                        logger.info(
                            "Recording command launched pid=%s: %s",
                            self._process.pid,
                            " ".join(args),
                        )
                        if cmd == "rpicam-vid":
                            logger.warning(
                                "ffmpeg not found; MP4 output may be corrupt when stopping by signal"
                            )
                except Exception as e:
                    self._last_error = str(e)
                    logger.warning("Recording start failed: %s", e)
                    self._stop_telemetry_writer()
                    self._stop_recording_stream()
                    if self._process is not None:
                        try:
                            self._process.kill()
                            self._process.wait()
                        except Exception:
                            pass
                    if self._muxer_process is not None:
                        try:
                            self._muxer_process.kill()
                            self._muxer_process.wait()
                        except Exception:
                            pass
                    self._process = None
                    self._muxer_process = None
                    self._output_path = None
                    return (self._idle_state(), str(e))

            # 5. Verify child liveness
            time.sleep(_LIVENESS_POLL_SEC)
            if self._process is not None and self._process.poll() is not None:
                pid = self._process.pid
                exit_code = self._process.returncode
                err = _read_process_stderr(self._process) or "Process exited"
                err_msg = f"exit_code={exit_code}: {err}"
                self._last_error = err_msg
                self._stop_telemetry_writer()
                self._stop_recording_stream()
                if self._muxer_process is not None:
                    _wait_and_terminate(self._muxer_process, _MUXER_WAIT_SEC)
                    self._muxer_process = None
                self._process = None
                self._output_path = None
                self._started_at = None
                logger.warning(
                    "Recording process exited early pid=%s exit_code=%s: %s",
                    pid,
                    exit_code,
                    err,
                )
                return (self._idle_state(), err_msg)
            if (
                self._muxer_process is not None
                and self._muxer_process.poll() is not None
            ):
                pid = self._muxer_process.pid
                exit_code = self._muxer_process.returncode
                err = _read_process_stderr(self._muxer_process) or "Process exited"
                err_msg = f"muxer_exit_code={exit_code}: {err}"
                self._last_error = err_msg
                self._stop_telemetry_writer()
                self._stop_recording_stream()
                if self._process is not None:
                    _wait_and_terminate(self._process, _TERMINATE_WAIT_SEC)
                    self._process = None
                self._muxer_process = None
                self._output_path = None
                self._started_at = None
                logger.warning(
                    "Recording muxer exited early pid=%s exit_code=%s: %s",
                    pid,
                    exit_code,
                    err,
                )
                return (self._idle_state(), err_msg)

            # 6. Finalize success
            self._started_at = datetime.now(timezone.utc)
            self._last_error = None
            basename = self._output_path.name
            logger.info("Recording started (%s): %s", cmd, basename)
            session_id = self._session_ref[0] if self._session_ref else None
            persist_enabled = get_recording_ai_persist_enabled()
            # Overlay and persist both use Hailo; only one can run. Skip ingest when overlay on.
            if persist_enabled and get_recording_ai_overlay_enabled():
                logger.info(
                    "Recording AI persist skipped: overlay enabled (Hailo device in use). "
                    "Disable overlay for persist detections."
                )
                persist_enabled = False
            if persist_enabled and session_id is None:
                logger.info(
                    "Recording AI persist skipped: no active session. Start session before recording for detections."
                )
            if (
                persist_enabled
                and self._output_path is not None
                and self._session_ref is not None
                and self._persistence is not None
                and session_id is not None
            ):
                # Fail fast: only create ingest when session is active. Avoids spinning
                # a thread that will always skip persist.

                def _get_sid() -> Optional[int]:
                    return self._session_ref[0] if self._session_ref else None

                self._ingest = RecordingAiIngest(
                    output_path=self._output_path,
                    get_session_id=_get_sid,
                    persistence=self._persistence,
                    get_state=self._get_state,
                )
                self._ingest.start()
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
                self._stop_telemetry_writer()
                self._stop_recording_stream()
                if self._ingest is not None:
                    self._ingest.stop()
                    self._ingest = None
                if self._muxer_process is not None:
                    _wait_and_terminate(self._muxer_process, _MUXER_WAIT_SEC)
                    self._muxer_process = None
                self._process = None
                self._output_path = None
                self._started_at = None
                return (self._idle_state(), None)
            if self._ingest is not None:
                self._ingest.stop()
                self._ingest = None
            self._stop_telemetry_writer()
            self._stop_recording_stream()
            # SIGTERM: rpicam-vid may finalize MP4 if given enough time. SIGINT when run as systemd child
            # can exit without writing; --signal has limited MP4 support on Pi 5.
            _wait_and_terminate(self._process, _TERMINATE_WAIT_SEC)
            if self._muxer_process is not None:
                _wait_and_terminate(self._muxer_process, _MUXER_WAIT_SEC)
                mux_rc = self._muxer_process.returncode
                mux_pid = self._muxer_process.pid
                err = _read_process_stderr(self._muxer_process) or "no stderr"
                self._muxer_process = None
                if mux_rc not in (0, None):
                    self._last_error = f"muxer_exit_code={mux_rc}: {err}"
                    logger.warning(
                        "Recording muxer exited with error pid=%s exit_code=%s: %s",
                        mux_pid,
                        mux_rc,
                        err,
                    )
            if basename:
                self._last_recorded_file = basename
                full_path = self._recordings_dir / basename
                size_bytes = full_path.stat().st_size if full_path.is_file() else None
                logger.info(
                    "Recording stopped: %s path=%s size=%s",
                    basename,
                    str(full_path.resolve()),
                    f"{size_bytes} bytes" if size_bytes is not None else "missing",
                )
            self._process = None
            self._output_path = None
            self._started_at = None
            return (self._idle_state(), None)

    def stop_and_cleanup(self) -> None:
        """Terminate active recording on app shutdown."""
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._stop_telemetry_writer()
                self._stop_recording_stream()
                if self._muxer_process is not None:
                    _wait_and_terminate(self._muxer_process, _MUXER_WAIT_SEC)
                    self._muxer_process = None
                return
            self._stop_telemetry_writer()
            self._stop_recording_stream()
            _wait_and_terminate(self._process, _TERMINATE_WAIT_SEC)
            self._process = None
            if self._muxer_process is not None:
                _wait_and_terminate(self._muxer_process, _MUXER_WAIT_SEC)
                self._muxer_process = None
            self._output_path = None
            self._started_at = None


class RecordingAutoController:
    """Edge-triggered auto recording based on armed state.

    recording_mode: off | manual | auto (not MAV flight mode).
    If the app starts while the aircraft is already armed, recording begins
    on the first armed state (intentional).
    """

    def __init__(
        self,
        service: CameraRecordingService,
        get_mode_fn: Callable[[], str],
        debounce_sec: Optional[float] = None,
        session_ref: Optional[List[Optional[int]]] = None,
    ) -> None:
        self._service = service
        self._get_mode = get_mode_fn
        self._debounce_sec = (
            debounce_sec
            if debounce_sec is not None
            else get_camera_recording_disarm_debounce_sec()
        )
        self._session_ref = session_ref
        self._last_armed: Optional[bool] = None
        self._disarm_since: Optional[float] = None

    def maybe_auto_record(self, state: "AircraftState") -> None:
        """Call from telemetry loop. Start/stop based on armed transitions in auto mode."""
        recording_mode = self._get_mode()
        if recording_mode != "auto":
            return
        armed = state.armed
        rec_state = self._service.get_recording_state()

        if armed:
            self._disarm_since = None
            if (
                self._last_armed is None or not self._last_armed
            ) and not rec_state.recording:
                new_state, err = self._service.start_recording()
                if err is None and new_state.output_file:
                    logger.info(
                        "Auto recording started (armed): %s", new_state.output_file
                    )
                elif err:
                    logger.warning("Auto recording start failed: %s", err)
        elif self._last_armed and rec_state.recording:
            if not state.connected:
                logger.debug(
                    "Armed transition ignored: disconnected/stale (holding last armed)"
                )
                return
            now = time.monotonic()
            if self._disarm_since is None:
                self._disarm_since = now
            if (
                self._debounce_sec <= 0
                or (now - self._disarm_since) >= self._debounce_sec
            ):
                logger.info(
                    "Auto-stop triggered (disarm confirmed after %.1fs): %s",
                    self._debounce_sec,
                    rec_state.output_file or "recording",
                )
                new_state, err = self._service.stop_recording()
                self._disarm_since = None
                if (
                    err is None
                    and new_state.last_recorded_file
                    and self._session_ref is not None
                    and self._session_ref[0] is not None
                ):
                    basename = new_state.last_recorded_file
                    video_path = Path(self._service.recordings_dir) / basename
                    if video_path.is_file():
                        self._service.mark_as_auto(basename, self._session_ref[0])
            else:
                return
        else:
            self._disarm_since = None

        self._last_armed = armed
