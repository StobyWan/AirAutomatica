"""User settings persistence. Loads from ~/.airautomatica/settings.json on startup."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from airautomatica.config import (
    get_ai_hat_camera_pipeline_enabled,
    get_ai_hat_enabled,
    get_ai_hat_object_detection_enabled,
    get_ai_hat_require_hardware,
    get_local_llm_provider,
    get_preprocessing_enabled,
    get_session_auto_start_on_arm,
)

logger = logging.getLogger(__name__)

_SETTINGS_DIR = Path.home() / ".airautomatica"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

# Whether LOCAL_LLM_PROVIDER was explicitly set (file or env) vs discovered at runtime.
_provider_explicit: bool = True

# Apply mode per setting: live (immediate), reconnect (subsystem reload), restart (full app).
ApplyMode = Literal["live", "reconnect", "restart"]
SETTING_APPLY_MODES: dict[str, ApplyMode] = {
    "TELEMETRY_BACKEND": "restart",
    "SERIAL_PORT": "restart",
    "SERIAL_BAUD": "restart",
    "LOCAL_LLM_PROVIDER": "reconnect",
    "LOCAL_LLM_BASE_URL": "reconnect",
    "LOCAL_LLM_MODEL": "reconnect",
    "LOCAL_LLM_TIMEOUT": "reconnect",
    "OLLAMA_NUM_THREAD": "reconnect",
    "AI_HAT_ENABLED": "restart",
    "AI_HAT_REQUIRE_HARDWARE": "restart",
    "AI_HAT_CAMERA_PIPELINE_ENABLED": "restart",
    "AI_HAT_OBJECT_DETECTION_ENABLED": "restart",
    "AI_HAT_DETECTION_THRESHOLD": "live",
    "AIRAUTOMATICA_PREPROCESSING_ENABLED": "restart",
    "AI_MIN_CONFIDENCE": "reconnect",
    "AI_DUPLICATE_WINDOW_SEC": "reconnect",
    "AI_SCHEDULER_COOLDOWN_SEC": "live",
    "CAMERA_RECORDING_MODE": "live",
    "SESSION_AUTO_START_ON_ARM": "live",
}

# Keys that trigger AI subsystem hot-reload when _reload_ai_fn is available.
AI_SUBSYSTEM_KEYS = frozenset(
    {
        "LOCAL_LLM_PROVIDER",
        "LOCAL_LLM_BASE_URL",
        "LOCAL_LLM_MODEL",
        "LOCAL_LLM_TIMEOUT",
        "OLLAMA_NUM_THREAD",
    }
)

# Keys that trigger telemetry reconnect when _reload_telemetry_fn is available.
TELEMETRY_SUBSYSTEM_KEYS = frozenset(
    {"TELEMETRY_BACKEND", "SERIAL_PORT", "SERIAL_BAUD"}
)

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
    "AI_HAT_REQUIRE_HARDWARE",
    "AI_HAT_CAMERA_PIPELINE_ENABLED",
    "AI_HAT_OBJECT_DETECTION_ENABLED",
    "AI_HAT_DETECTION_THRESHOLD",
    "AIRAUTOMATICA_PREPROCESSING_ENABLED",
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
    """Load settings from file into os.environ. Call before any config is read.
    When LOCAL_LLM_PROVIDER is unset, discovers Ollama at runtime and sets
    effective provider (ollama if ready, mock otherwise). Does not persist discovery."""
    global _provider_explicit
    provider_explicit_before = bool(os.environ.get("LOCAL_LLM_PROVIDER", "").strip())
    data: dict = {}
    if _SETTINGS_FILE.exists():
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
            provider_explicit_before = (
                provider_explicit_before
                or bool(data.get("LOCAL_LLM_PROVIDER"))
                or bool(data.get("AI_MODE") or data.get("AI_BACKEND"))
            )
        except Exception as e:
            logger.warning("Failed to load settings from %s: %s", _SETTINGS_FILE, e)

    if not provider_explicit_before:
        from airautomatica.ai.ollama_readiness import check_ollama_ready

        base = os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434")
        model = os.environ.get("LOCAL_LLM_MODEL", "gemma3:1b")
        result = check_ollama_ready(base, model=model, timeout_sec=2.0)
        effective = "ollama" if result.ready else "mock"
        os.environ["LOCAL_LLM_PROVIDER"] = effective
        _provider_explicit = False
        logger.info(
            "AI provider unset; discovered %s (ollama_ready=%s)",
            effective,
            result.ready,
        )
    else:
        _provider_explicit = True


def get_raw_settings() -> dict:
    """Return raw saved settings: file content + env for keys not in file.
    For LOCAL_LLM_PROVIDER when unset (discovered at runtime), returns empty string."""
    defaults: dict[str, str] = {
        "TELEMETRY_BACKEND": "mock",
        "SERIAL_PORT": "/dev/ttyUSB0",
        "SERIAL_BAUD": "921600",
        "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434",
        "LOCAL_LLM_MODEL": "gemma3:1b",
        "LOCAL_LLM_TIMEOUT": "30",
        "OLLAMA_NUM_THREAD": "4",
        "AI_HAT_ENABLED": "0",
        "AI_HAT_REQUIRE_HARDWARE": "0",
        "AI_HAT_CAMERA_PIPELINE_ENABLED": "0",
        "AI_HAT_OBJECT_DETECTION_ENABLED": "0",
        "AI_HAT_DETECTION_THRESHOLD": "0.25",
        "AIRAUTOMATICA_PREPROCESSING_ENABLED": "1",
        "AI_MIN_CONFIDENCE": "0.5",
        "AI_DUPLICATE_WINDOW_SEC": "30",
        "AI_SCHEDULER_COOLDOWN_SEC": "8",
        "CAMERA_RECORDING_MODE": "manual",
        "SESSION_AUTO_START_ON_ARM": "0",
    }
    file_data: dict = {}
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE) as f:
                file_data = {
                    k: str(v)
                    for k, v in json.load(f).items()
                    if k in CANONICAL_SETTINGS_KEYS and v is not None
                }
        except Exception:
            pass

    result: dict[str, str] = {}
    for k in CANONICAL_SETTINGS_KEYS:
        if k in file_data:
            result[k] = file_data[k]
        elif k == "LOCAL_LLM_PROVIDER":
            if _provider_explicit:
                result[k] = get_local_llm_provider()
            else:
                result[k] = ""  # Unset; discovered at runtime
        elif k == "AI_HAT_ENABLED":
            result[k] = "1" if get_ai_hat_enabled() else "0"
        elif k == "AI_HAT_REQUIRE_HARDWARE":
            result[k] = "1" if get_ai_hat_require_hardware() else "0"
        elif k == "AI_HAT_CAMERA_PIPELINE_ENABLED":
            result[k] = "1" if get_ai_hat_camera_pipeline_enabled() else "0"
        elif k == "AI_HAT_OBJECT_DETECTION_ENABLED":
            result[k] = "1" if get_ai_hat_object_detection_enabled() else "0"
        elif k == "AIRAUTOMATICA_PREPROCESSING_ENABLED":
            result[k] = "1" if get_preprocessing_enabled() else "0"
        elif k == "SESSION_AUTO_START_ON_ARM":
            result[k] = "1" if get_session_auto_start_on_arm() else "0"
        else:
            result[k] = os.environ.get(k, defaults.get(k, ""))
    return result


def get_effective_settings() -> dict:
    """Return effective runtime settings including discovered defaults.
    Use for display when showing current runtime behavior."""
    raw = get_raw_settings()
    effective = dict(raw)
    # Effective provider: explicit value or discovered (already in env)
    if raw.get("LOCAL_LLM_PROVIDER") == "":
        effective["LOCAL_LLM_PROVIDER"] = get_local_llm_provider()
    return effective


def get_settings() -> dict:
    """Return current settings as canonical keys only. Uses config getters for
    LOCAL_LLM_PROVIDER and AI_HAT_ENABLED so legacy AI_MODE is correctly derived.
    Returns effective values (includes discovered provider when unset)."""
    return get_effective_settings()


def get_apply_modes() -> dict[str, ApplyMode]:
    """Return apply mode for each canonical setting."""
    return dict(SETTING_APPLY_MODES)


def get_provider_reason() -> str:
    """Return why the current AI provider was chosen.
    Values: explicit_mock, explicit_ollama, discovered_ollama_ready, discovered_mock_ollama_unavailable.
    """
    provider = get_local_llm_provider()
    if _provider_explicit:
        return f"explicit_{provider}"
    if provider == "ollama":
        return "discovered_ollama_ready"
    return "discovered_mock_ollama_unavailable"


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
