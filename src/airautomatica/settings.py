"""User settings persistence. Loads from ~/.airautomatica/settings.json on startup."""

import json
import logging
import os
from pathlib import Path

from airautomatica.config import get_ai_hat_enabled, get_local_llm_provider

logger = logging.getLogger(__name__)

_SETTINGS_DIR = Path.home() / ".airautomatica"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

# Canonical keys: returned by GET /settings and persisted on save. No legacy keys.
CANONICAL_SETTINGS_KEYS = [
    "TELEMETRY_BACKEND",
    "SERIAL_PORT",
    "SERIAL_BAUD",
    "LOCAL_LLM_PROVIDER",
    "LOCAL_LLM_BASE_URL",
    "LOCAL_LLM_MODEL",
    "LOCAL_LLM_TIMEOUT",
    "LM_STUDIO_BASE_URL",
    "LM_STUDIO_MODEL",
    "AI_HAT_ENABLED",
    "AI_MIN_CONFIDENCE",
    "AI_DUPLICATE_WINDOW_SEC",
]

# Legacy keys accepted when loading from file or in POST body; never persisted.
_LEGACY_KEYS = ("AI_MODE", "AI_BACKEND")

# All keys accepted when loading from file (canonical + legacy)
_LOAD_ACCEPTED_KEYS = frozenset(CANONICAL_SETTINGS_KEYS) | frozenset(_LEGACY_KEYS)

# Backward compat: SETTINGS_KEYS used by existing code (e.g. tests that patch)
SETTINGS_KEYS = CANONICAL_SETTINGS_KEYS


def _migrate_legacy_to_canonical(data: dict) -> dict:
    """Map legacy keys to canonical. Used for load (runtime) and save (persistence).
    AI_MODE=ollama -> LOCAL_LLM_PROVIDER=ollama
    AI_MODE=aihat -> AI_HAT_ENABLED=1, LOCAL_LLM_PROVIDER=mock
    AI_MODE=lmstudio -> LOCAL_LLM_PROVIDER=lmstudio
    AI_MODE=mock -> LOCAL_LLM_PROVIDER=mock
    """
    out = dict(data)
    mode = (out.get("AI_MODE") or out.get("AI_BACKEND") or "").lower()

    if mode and not out.get("LOCAL_LLM_PROVIDER"):
        if mode == "ollama":
            out["LOCAL_LLM_PROVIDER"] = "ollama"
        elif mode == "aihat":
            out["LOCAL_LLM_PROVIDER"] = "mock"
            out["AI_HAT_ENABLED"] = "1"
        elif mode == "lmstudio":
            out["LOCAL_LLM_PROVIDER"] = "lmstudio"
        elif mode == "mock":
            out["LOCAL_LLM_PROVIDER"] = "mock"

    if mode == "aihat" and "AI_HAT_ENABLED" not in out:
        out["AI_HAT_ENABLED"] = "1"

    return out


def load_settings() -> None:
    """Load settings from file into os.environ. Call before any config is read."""
    if not _SETTINGS_FILE.exists():
        return
    try:
        with open(_SETTINGS_FILE) as f:
            data = json.load(f)
        for k, v in data.items():
            if k in _LOAD_ACCEPTED_KEYS and v is not None:
                os.environ[k] = str(v)
    except Exception as e:
        logger.warning("Failed to load settings from %s: %s", _SETTINGS_FILE, e)


def get_settings() -> dict:
    """Return current settings as canonical keys only. Uses config getters for
    LOCAL_LLM_PROVIDER and AI_HAT_ENABLED so legacy AI_MODE is correctly derived."""
    defaults: dict[str, str] = {
        "TELEMETRY_BACKEND": "mock",
        "SERIAL_PORT": "/dev/ttyUSB0",
        "SERIAL_BAUD": "921600",
        "LOCAL_LLM_PROVIDER": "mock",
        "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434",
        "LOCAL_LLM_MODEL": "gemma3:1b",
        "LOCAL_LLM_TIMEOUT": "30",
        "LM_STUDIO_BASE_URL": "http://localhost:1234",
        "LM_STUDIO_MODEL": "local-model",
        "AI_HAT_ENABLED": "0",
        "AI_MIN_CONFIDENCE": "0.5",
        "AI_DUPLICATE_WINDOW_SEC": "30",
    }
    result: dict[str, str] = {}
    for k in CANONICAL_SETTINGS_KEYS:
        if k == "LOCAL_LLM_PROVIDER":
            result[k] = get_local_llm_provider()
        elif k == "AI_HAT_ENABLED":
            result[k] = "1" if get_ai_hat_enabled() else "0"
        else:
            result[k] = os.environ.get(k, defaults.get(k, ""))
    return result


def save_settings(updates: dict) -> None:
    """Merge updates into settings file. Writes canonical keys only.
    Accepts legacy keys (AI_MODE, AI_BACKEND) in updates and maps to canonical;
    never persists legacy keys. Does not affect running app; restart required."""
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    current: dict = {}
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE) as f:
                data = json.load(f)
            current = {
                k: v
                for k, v in data.items()
                if k in CANONICAL_SETTINGS_KEYS and v is not None
            }
        except Exception:
            pass
    migrated = _migrate_legacy_to_canonical(dict(updates))
    for k, v in migrated.items():
        if k in CANONICAL_SETTINGS_KEYS:
            if v is None or v == "":
                current.pop(k, None)
            else:
                current[k] = str(v).strip()
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(current, f, indent=2)
