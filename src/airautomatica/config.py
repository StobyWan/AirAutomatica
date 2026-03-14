"""Configuration from environment variables."""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_lmstudio_warned = False


def get_ai_mode() -> str:
    """AI mode: 'mock', 'ollama', or 'aihat'. Default: mock.
    Env: AI_MODE or AI_BACKEND (legacy)."""
    return os.environ.get("AI_MODE", os.environ.get("AI_BACKEND", "mock")).lower()


def get_ai_backend() -> str:
    """Legacy alias for get_ai_mode()."""
    return get_ai_mode()


def _warn_lmstudio_once() -> None:
    global _lmstudio_warned
    if not _lmstudio_warned:
        _lmstudio_warned = True
        logger.warning(
            "LOCAL_LLM_PROVIDER=lmstudio is no longer supported; falling back to mock"
        )


def get_local_llm_provider() -> str:
    """Local LLM provider: 'mock' or 'ollama'. Default: ollama.
    When LOCAL_LLM_PROVIDER is set and in (mock, ollama), use it.
    Else use AI_MODE/AI_BACKEND if set (legacy); when AI_MODE=aihat, base is mock.
    lmstudio (legacy) logs a warning once and falls back to mock.
    When nothing is set, returns ollama as canonical default."""
    provider = os.environ.get("LOCAL_LLM_PROVIDER", "").lower()
    if provider in ("mock", "ollama"):
        return provider
    if provider == "lmstudio":
        _warn_lmstudio_once()
        return "mock"
    # Legacy: AI_MODE or AI_BACKEND explicitly set
    if (
        os.environ.get("AI_MODE") is not None
        or os.environ.get("AI_BACKEND") is not None
    ):
        mode = get_ai_mode()
        if mode in ("mock", "ollama"):
            return mode
        if mode == "lmstudio":
            _warn_lmstudio_once()
            return "mock"
        # AI_MODE=aihat: use mock as base provider
        return "mock"
    # Nothing set: canonical default
    return "ollama"


def get_ai_hat_enabled() -> bool:
    """True if AI HAT layer should be enabled alongside local LLM provider.
    Env: AI_HAT_ENABLED (1/true/yes) or legacy AI_MODE=aihat."""
    explicit = os.environ.get("AI_HAT_ENABLED", "").lower()
    if explicit in ("1", "true", "yes"):
        return True
    if explicit in ("0", "false", "no"):
        return False
    return get_ai_mode() == "aihat"


def get_effective_ai_backend() -> str:
    """Return effective AI backend(s) for session/logging/health.
    Format: 'mock', 'ollama', 'mock+aihat', or 'ollama+aihat'."""
    base = get_local_llm_provider()
    if get_ai_hat_enabled():
        return f"{base}+aihat"
    return base


def get_local_llm_base_url(provider: str) -> str:
    """Base URL for local LLM. For ollama default http://127.0.0.1:11434; for mock unused."""
    if provider == "ollama":
        return os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434")
    return ""


def get_local_llm_model(provider: str) -> str:
    """Model name for local LLM. For ollama default gemma3:1b; for mock unused."""
    if provider == "ollama":
        return os.environ.get("LOCAL_LLM_MODEL", "gemma3:1b")
    return ""


def get_local_llm_timeout() -> float:
    """Local LLM request timeout in seconds. Default: 30.0."""
    try:
        return float(os.environ.get("LOCAL_LLM_TIMEOUT", "30.0"))
    except ValueError:
        return 30.0


def get_ollama_required() -> bool:
    """True if startup should fail when Ollama is not ready. Default: False (degraded mode).
    Env: AIRAUTOMATICA_OLLAMA_REQUIRED (wins) or OLLAMA_REQUIRED.
    Precedence: AIRAUTOMATICA_* overrides plain OLLAMA_*."""
    raw = os.environ.get(
        "AIRAUTOMATICA_OLLAMA_REQUIRED",
        os.environ.get("OLLAMA_REQUIRED", "0"),
    ).lower()
    return raw in ("1", "true", "yes")


def get_ollama_num_thread() -> int:
    """Number of CPU threads Ollama uses for inference. 1-8. Default 4.
    Lower values reduce Pi 5 CPU load and thermals."""
    raw = os.environ.get(
        "AIRAUTOMATICA_OLLAMA_NUM_THREAD",
        os.environ.get("OLLAMA_NUM_THREAD", "4"),
    )
    try:
        val = int(raw)
        return max(1, min(8, val))
    except ValueError:
        return 4


def get_aihat_model_name() -> str:
    """AI HAT model name. Default: default."""
    return os.environ.get("AIHAT_MODEL_NAME", "default")


def get_aihat_device() -> str:
    """AI HAT device config. Default: auto.
    Placeholder: AI HAT+ uses PCIe; HailoRT auto-discovers. Unused until real integration.
    """
    return os.environ.get("AIHAT_DEVICE", "auto")


def get_ai_hat_require_hardware() -> bool:
    """True if startup should fail when Hailo not detected. Default: False.
    When True and Hailo not detected, log warning but do not fail startup."""
    raw = os.environ.get("AI_HAT_REQUIRE_HARDWARE", "0").lower().strip()
    return raw in ("1", "true", "yes")


def get_ai_hat_camera_pipeline_enabled() -> bool:
    """True if AI HAT camera pipeline is enabled. Default: True when AI HAT enabled."""
    if not get_ai_hat_enabled():
        return False
    raw = os.environ.get("AI_HAT_CAMERA_PIPELINE_ENABLED", "1").lower().strip()
    return raw in ("1", "true", "yes")


def get_ai_hat_object_detection_enabled() -> bool:
    """True if AI HAT object detection is enabled. Default: True when AI HAT enabled."""
    if not get_ai_hat_enabled():
        return False
    raw = os.environ.get("AI_HAT_OBJECT_DETECTION_ENABLED", "1").lower().strip()
    return raw in ("1", "true", "yes")


def get_ai_hat_detection_threshold() -> float:
    """Min confidence for AI HAT detections. 0.0-1.0. Default: 0.25.
    Suppresses weak detections below this threshold. Separate from AI_MIN_CONFIDENCE (mission logic).
    """
    try:
        v = float(os.environ.get("AI_HAT_DETECTION_THRESHOLD", "0.25"))
        return max(0.0, min(1.0, v))
    except ValueError:
        return 0.25


def get_ai_min_confidence() -> float:
    """Min confidence to accept a detection. 0.0-1.0. Default: 0.5."""
    try:
        v = float(os.environ.get("AI_MIN_CONFIDENCE", "0.5"))
        return max(0.0, min(1.0, v))
    except ValueError:
        return 0.5


def get_ai_duplicate_window_sec() -> float:
    """Seconds within which same label is suppressed as duplicate. Default: 30."""
    try:
        return float(os.environ.get("AI_DUPLICATE_WINDOW_SEC", "30.0"))
    except ValueError:
        return 30.0


def get_ai_scheduler_cooldown_sec() -> float:
    """Base cooldown between Ollama jobs (seconds). Default: 8. Applies without restart when changed via Settings."""
    try:
        return max(0.0, float(os.environ.get("AI_SCHEDULER_COOLDOWN_SEC", "8.0")))
    except ValueError:
        return 8.0


def get_telemetry_backend() -> str:
    """Telemetry backend: 'mock' or 'serial'. Default: mock."""
    return os.environ.get("TELEMETRY_BACKEND", "mock").lower()


def get_serial_port() -> str:
    """Serial port for MAVLink. Default: /dev/ttyUSB0 (Pi 5, CP2102/FTDI).
    Bench setup: Pi 5 + CP2102 USB-TTL + Matek F405-WING V2.
    FC UART (TELEM1/2) -> CP2102 -> Pi USB -> /dev/ttyUSB0.
    Native USB devices often use /dev/ttyACM0.
    See docs/example_hardware.md and docs/hardware_hookup.md."""
    return os.environ.get("SERIAL_PORT", "/dev/ttyUSB0")


def get_serial_baud() -> int:
    """Serial baud rate. Default: 921600 for companion-computer (USB/UART).
    Use SERIAL_BAUD=57600 for telemetry radios."""
    try:
        return int(os.environ.get("SERIAL_BAUD", "921600"))
    except ValueError:
        return 921600


def validate_serial_config(backend: str, port: str) -> tuple[bool, str | None]:
    """Validate serial config before reconnect. Returns (ok, error_message).
    For mock backend, always ok. For serial, checks port exists on Unix."""
    if backend != "serial":
        return True, None
    if not port or not port.strip():
        return False, "Serial port is required when using serial backend"
    port_path = Path(port.strip())
    if sys.platform in ("linux", "darwin") and not port_path.exists():
        return False, f"Serial port {port!r} not found"
    return True, None


def get_api_host() -> str:
    """API server bind host. Default: 0.0.0.0."""
    return os.environ.get("API_HOST", "0.0.0.0")


def get_api_port() -> int:
    """API server port. Default: 8000."""
    try:
        return int(os.environ.get("API_PORT", "8000"))
    except ValueError:
        return 8000


def get_sqlite_db_path() -> str:
    """SQLite database path. Default: ~/.airautomatica/airautomatica.db"""
    default = os.path.expanduser("~/.airautomatica/airautomatica.db")
    return os.environ.get("SQLITE_DB_PATH", default)


def get_recordings_dir() -> str:
    """Recordings directory for camera video files. Default: ~/.airautomatica/recordings.
    Always returns an absolute path (resolved, expanduser applied)."""
    raw = (
        os.environ.get("AIRAUTOMATICA_RECORDINGS_DIR")
        or os.environ.get("RECORDINGS_DIR")
        or os.path.expanduser("~/.airautomatica/recordings")
    )
    return str(Path(raw).expanduser().resolve())


def get_camera_recording_mode() -> str:
    """Camera recording mode: off, manual, or auto. Default: manual.
    Env: CAMERA_RECORDING_MODE (also from settings.json). Uses persisted settings for live updates.
    """
    try:
        from airautomatica.settings import get_raw_settings

        raw = get_raw_settings().get("CAMERA_RECORDING_MODE") or os.environ.get(
            "CAMERA_RECORDING_MODE", "manual"
        )
    except Exception:
        raw = os.environ.get("CAMERA_RECORDING_MODE", "manual")
    raw = str(raw).lower().strip()
    if raw in ("off", "manual", "auto"):
        return raw
    return "manual"


def get_camera_recording_disarm_debounce_sec() -> float:
    """Seconds armed=False must persist before auto-stop. Default: 2.5.
    Reduces false stops from telemetry jitter or brief disconnects.
    Env: CAMERA_RECORDING_DISARM_DEBOUNCE_SEC."""
    try:
        return max(
            0.0, float(os.environ.get("CAMERA_RECORDING_DISARM_DEBOUNCE_SEC", "2.5"))
        )
    except ValueError:
        return 2.5


def get_session_auto_start_on_arm() -> bool:
    """True if session should auto-start when armed and auto-stop when disarmed.
    Default: False. Env: SESSION_AUTO_START_ON_ARM (1/true/yes)."""
    raw = os.environ.get("SESSION_AUTO_START_ON_ARM", "0").lower().strip()
    return raw in ("1", "true", "yes")


def get_preprocessing_enabled() -> bool:
    """True if telemetry preprocessing pipeline is enabled. Default: True.
    Env: AIRAUTOMATICA_PREPROCESSING_ENABLED (1/true/yes)."""
    raw = os.environ.get("AIRAUTOMATICA_PREPROCESSING_ENABLED", "1").lower().strip()
    return raw in ("1", "true", "yes")


def get_session_auto_stop_disarm_debounce_sec() -> float:
    """Seconds armed=False must persist before auto-stop. Default: 2.5.
    Env: SESSION_AUTO_STOP_DISARM_DEBOUNCE_SEC."""
    try:
        return max(
            0.0,
            float(os.environ.get("SESSION_AUTO_STOP_DISARM_DEBOUNCE_SEC", "2.5")),
        )
    except ValueError:
        return 2.5
