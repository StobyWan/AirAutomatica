"""User settings persistence. Loads from ~/.airautomatica/settings.json on startup."""

import json
import logging
import os
from pathlib import Path

from airautomatica.config import (
    get_ai_hat_enabled,
    get_local_llm_provider,
    get_session_auto_start_on_arm,
)

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
    "OLLAMA_NUM_THREAD",
    "AI_HAT_ENABLED",
    "AI_MIN_CONFIDENCE",
    "AI_DUPLICATE_WINDOW_SEC",
    "AI_SCHEDULER_COOLDOWN_SEC",
    "CAMERA_RECORDING_MODE",
    "SESSION_AUTO_START_ON_ARM",
]

# Legacy keys accepted when loading from file or in POST body; never persisted.
_LEGACY_KEYS = ("AI_MODE", "AI_BACKEND")

# LM Studio keys: accepted on load only (old settings files); not canonical, not exposed.
_LOAD_ONLY_KEYS = frozenset({"LM_STUDIO_BASE_URL", "LM_STUDIO_MODEL"})

# All keys accepted when loading from file
_LOAD_ACCEPTED_KEYS = (
    frozenset(CANONICAL_SETTINGS_KEYS) | frozenset(_LEGACY_KEYS) | _LOAD_ONLY_KEYS
)

# Backward compat: SETTINGS_KEYS used by existing code (e.g. tests that patch)
SETTINGS_KEYS = CANONICAL_SETTINGS_KEYS


def _migrate_legacy_to_canonical(data: dict) -> dict:
    """Map legacy keys to canonical. Used for load (runtime) and save (persistence).
    AI_MODE=ollama -> LOCAL_LLM_PROVIDER=ollama
    AI_MODE=aihat -> AI_HAT_ENABLED=1, LOCAL_LLM_PROVIDER=mock
    AI_MODE=lmstudio -> LOCAL_LLM_PROVIDER=mock
    AI_MODE=mock -> LOCAL_LLM_PROVIDER=mock
    LOCAL_LLM_PROVIDER=lmstudio -> mock (no longer supported)
    """
    out = dict(data)
    # Map deprecated lmstudio to mock when present in updates
    if (out.get("LOCAL_LLM_PROVIDER") or "").lower() == "lmstudio":
        out["LOCAL_LLM_PROVIDER"] = "mock"
    mode = (out.get("AI_MODE") or out.get("AI_BACKEND") or "").lower()

    if mode and not out.get("LOCAL_LLM_PROVIDER"):
        if mode == "ollama":
            out["LOCAL_LLM_PROVIDER"] = "ollama"
        elif mode == "aihat":
            out["LOCAL_LLM_PROVIDER"] = "mock"
            out["AI_HAT_ENABLED"] = "1"
        elif mode == "lmstudio":
            out["LOCAL_LLM_PROVIDER"] = "mock"
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
        if any(k in data for k in _LEGACY_KEYS):
            logger.debug(
                "Legacy AI_MODE/AI_BACKEND in settings; consider LOCAL_LLM_PROVIDER and AI_HAT_ENABLED"
            )
    except Exception as e:
        logger.warning("Failed to load settings from %s: %s", _SETTINGS_FILE, e)


def get_settings() -> dict:
    """Return current settings as canonical keys only. Uses config getters for
    LOCAL_LLM_PROVIDER and AI_HAT_ENABLED so legacy AI_MODE is correctly derived."""
    defaults: dict[str, str] = {
        "TELEMETRY_BACKEND": "mock",
        "SERIAL_PORT": "/dev/ttyUSB0",
        "SERIAL_BAUD": "921600",
        "LOCAL_LLM_PROVIDER": "ollama",
        "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434",
        "LOCAL_LLM_MODEL": "gemma3:1b",
        "LOCAL_LLM_TIMEOUT": "30",
        "OLLAMA_NUM_THREAD": "4",
        "AI_HAT_ENABLED": "0",
        "AI_MIN_CONFIDENCE": "0.5",
        "AI_DUPLICATE_WINDOW_SEC": "30",
        "AI_SCHEDULER_COOLDOWN_SEC": "8",
        "CAMERA_RECORDING_MODE": "manual",
        "SESSION_AUTO_START_ON_ARM": "0",
    }
    result: dict[str, str] = {}
    for k in CANONICAL_SETTINGS_KEYS:
        if k == "LOCAL_LLM_PROVIDER":
            result[k] = get_local_llm_provider()
        elif k == "AI_HAT_ENABLED":
            result[k] = "1" if get_ai_hat_enabled() else "0"
        elif k == "SESSION_AUTO_START_ON_ARM":
            result[k] = "1" if get_session_auto_start_on_arm() else "0"
        else:
            result[k] = os.environ.get(k, defaults.get(k, ""))
    return result


def save_settings(updates: dict) -> None:
    """Merge updates into settings file. Writes canonical keys only.
    Accepts legacy keys (AI_MODE, AI_BACKEND) in updates and maps to canonical;
    never persists legacy keys. Updates os.environ for runtime changes (e.g. AI_SCHEDULER_COOLDOWN_SEC).
    """
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
                os.environ.pop(k, None)
            else:
                val = str(v).strip()
                if k == "OLLAMA_NUM_THREAD":
                    try:
                        n = int(val)
                        val = str(max(1, min(8, n)))
                    except ValueError:
                        val = "4"
                current[k] = val
                os.environ[k] = current[k]
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(current, f, indent=2)
