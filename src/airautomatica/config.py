"""Configuration from environment variables."""

import os


def get_ai_mode() -> str:
    """AI mode: 'mock', 'lmstudio', or 'aihat'. Default: mock.
    Env: AI_MODE or AI_BACKEND (legacy)."""
    return os.environ.get("AI_MODE", os.environ.get("AI_BACKEND", "mock")).lower()


def get_ai_backend() -> str:
    """Legacy alias for get_ai_mode()."""
    return get_ai_mode()


def get_lm_studio_base_url() -> str:
    """LM Studio API base URL. Default: http://localhost:1234."""
    return os.environ.get("LM_STUDIO_BASE_URL", "http://localhost:1234")


def get_lm_studio_model() -> str:
    """LM Studio model name. Default: local-model."""
    return os.environ.get("LM_STUDIO_MODEL", "local-model")


def get_lm_studio_timeout() -> float:
    """LM Studio request timeout in seconds. Default: 30.0."""
    try:
        return float(os.environ.get("LM_STUDIO_TIMEOUT", "30.0"))
    except ValueError:
        return 30.0


def get_aihat_model_name() -> str:
    """AI HAT model name. Default: default."""
    return os.environ.get("AIHAT_MODEL_NAME", "default")


def get_aihat_device() -> str:
    """AI HAT device config. Default: auto.
    Placeholder: AI HAT+ uses PCIe; HailoRT auto-discovers. Unused until real integration.
    """
    return os.environ.get("AIHAT_DEVICE", "auto")


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


def get_telemetry_backend() -> str:
    """Telemetry backend: 'mock' or 'serial'. Default: mock."""
    return os.environ.get("TELEMETRY_BACKEND", "mock").lower()


def get_serial_port() -> str:
    """Serial port for MAVLink. Default: /dev/ttyACM0."""
    return os.environ.get("SERIAL_PORT", "/dev/ttyACM0")


def get_serial_baud() -> int:
    """Serial baud rate. Default: 921600 for companion-computer (USB/UART).
    Use SERIAL_BAUD=57600 for telemetry radios."""
    try:
        return int(os.environ.get("SERIAL_BAUD", "921600"))
    except ValueError:
        return 921600


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
