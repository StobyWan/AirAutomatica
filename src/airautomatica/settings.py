"""User settings persistence. Loads from ~/.airautomatica/settings.json on startup."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SETTINGS_DIR = Path.home() / ".airautomatica"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

# Keys that can be set via the dashboard
SETTINGS_KEYS = [
    "TELEMETRY_BACKEND",
    "AI_MODE",
    "SERIAL_PORT",
    "SERIAL_BAUD",
    "LM_STUDIO_BASE_URL",
    "LM_STUDIO_MODEL",
    "AI_MIN_CONFIDENCE",
    "AI_DUPLICATE_WINDOW_SEC",
]


def load_settings() -> None:
    """Load settings from file into os.environ. Call before any config is read."""
    if not _SETTINGS_FILE.exists():
        return
    try:
        with open(_SETTINGS_FILE) as f:
            data = json.load(f)
        for k, v in data.items():
            if k in SETTINGS_KEYS and v is not None:
                os.environ[k] = str(v)
    except Exception as e:
        logger.warning("Failed to load settings from %s: %s", _SETTINGS_FILE, e)


def get_settings() -> dict:
    """Return current settings (from env, which may have been set by load_settings)."""
    defaults = {
        "TELEMETRY_BACKEND": "mock",
        "AI_MODE": "mock",
        "SERIAL_PORT": "/dev/ttyACM0",
        "SERIAL_BAUD": "921600",
        "LM_STUDIO_BASE_URL": "http://localhost:1234",
        "LM_STUDIO_MODEL": "local-model",
        "AI_MIN_CONFIDENCE": "0.5",
        "AI_DUPLICATE_WINDOW_SEC": "30",
    }
    return {k: os.environ.get(k, defaults.get(k, "")) for k in SETTINGS_KEYS}


def save_settings(updates: dict) -> None:
    """Merge updates into settings file. Does not affect running app; restart required."""
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    current: dict = {}
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE) as f:
                current = json.load(f)
        except Exception:
            pass
    for k, v in updates.items():
        if k in SETTINGS_KEYS:
            if v is None or v == "":
                current.pop(k, None)
            else:
                current[k] = str(v).strip()
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(current, f, indent=2)
