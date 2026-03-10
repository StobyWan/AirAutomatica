"""Configuration from environment variables."""

import os


def get_ai_mode() -> str:
    """AI mode: 'mock', 'lmstudio', 'ollama', or 'aihat'. Default: mock.
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
    """LM Studio request timeout in seconds. Default: 30.0.
    Deprecated: use get_local_llm_timeout() for Ollama."""
    try:
        return float(os.environ.get("LM_STUDIO_TIMEOUT", "30.0"))
    except ValueError:
        return 30.0


def get_local_llm_provider() -> str:
    """Local LLM provider: 'mock', 'ollama', or 'lmstudio' (deprecated).
    When LOCAL_LLM_PROVIDER is set and in (mock, ollama, lmstudio), use it.
    Else use AI_MODE if mock/ollama/lmstudio; when AI_MODE=aihat (legacy), default to mock.
    """
    provider = os.environ.get("LOCAL_LLM_PROVIDER", "").lower()
    if provider in ("mock", "ollama", "lmstudio"):
        return provider
    mode = get_ai_mode()
    if mode in ("mock", "ollama", "lmstudio"):
        return mode
    # Legacy AI_MODE=aihat no longer means exclusive; use mock as base provider
    return "mock"


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
    """Serial port for MAVLink. Default: /dev/ttyACM0.
    CP2102/FTDI adapters typically use /dev/ttyUSB0; native USB often uses /dev/ttyACM0.
    See docs/example_hardware.md for a reference setup."""
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
