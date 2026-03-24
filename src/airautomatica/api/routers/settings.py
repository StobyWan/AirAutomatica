"""Settings routes: GET/POST settings."""

from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from fastapi import APIRouter, Body

from airautomatica.ai.ollama_readiness import check_ollama_ready
from airautomatica.api.helpers import build_active_summary
from airautomatica.config import (
    get_ai_duplicate_window_sec,
    get_ai_min_confidence,
    get_local_llm_base_url,
    get_local_llm_model,
    get_local_llm_provider,
    get_mock_telemetry_type,
    get_serial_baud,
    get_serial_port,
    get_telemetry_backend,
    validate_serial_config,
)
from airautomatica.runtime.ai_subsystem import ReloadResult
from airautomatica.runtime.telemetry_subsystem import TelemetryReconnectResult
from airautomatica.settings import (
    AI_SUBSYSTEM_KEYS,
    SETTING_APPLY_MODES,
    TELEMETRY_SUBSYSTEM_KEYS,
    get_apply_modes,
    get_effective_settings,
    get_provider_reason,
    get_raw_settings,
    save_settings,
)

if TYPE_CHECKING:
    from airautomatica.services.mission_logic import MissionLogic


def create_settings_router(
    mission_logic: Optional["MissionLogic"],
    reload_ai_fn: Optional[Callable[[str], ReloadResult]],
    reload_telemetry_fn: Optional[Callable[[], Awaitable[TelemetryReconnectResult]]],
) -> APIRouter:
    """Create settings router with injected dependencies."""
    router = APIRouter(tags=["settings"])

    @router.get("/settings")
    def get_settings_endpoint() -> dict:
        """Return raw saved settings, effective runtime settings, apply modes, and Ollama status."""
        raw = get_raw_settings()
        effective = get_effective_settings()
        apply_modes = dict(get_apply_modes())
        if mission_logic is not None:
            apply_modes["AI_MIN_CONFIDENCE"] = "live"
            apply_modes["AI_DUPLICATE_WINDOW_SEC"] = "live"
        if reload_ai_fn is not None:
            for k in AI_SUBSYSTEM_KEYS:
                apply_modes[k] = "live"
        if reload_telemetry_fn is not None:
            for k in TELEMETRY_SUBSYSTEM_KEYS:
                apply_modes[k] = "live"
        provider_reason = get_provider_reason()

        ollama_result = check_ollama_ready(
            get_local_llm_base_url("ollama"),
            model=get_local_llm_model("ollama"),
            timeout_sec=2.0,
        )
        ollama_ready = ollama_result.ready
        ollama_available = ollama_result.reason != "unreachable"

        active_summary = build_active_summary()

        return {
            "settings": raw,
            "effective_settings": effective,
            "apply_modes": apply_modes,
            "telemetry_reconnect_available": reload_telemetry_fn is not None,
            "ai_reconnect_available": reload_ai_fn is not None,
            "ollama_available": ollama_available,
            "ollama_ready": ollama_ready,
            "provider_reason": provider_reason,
            "active_summary": active_summary,
        }

    @router.post("/settings")
    async def post_settings(updates: dict = Body(...)) -> dict:
        """Save settings to file. Returns structured result with apply-mode info."""
        from airautomatica.settings import CANONICAL_SETTINGS_KEYS

        changed_keys = [k for k in updates if k in CANONICAL_SETTINGS_KEYS]
        provider_before = get_local_llm_provider()
        telemetry_subsystem_changed = TELEMETRY_SUBSYSTEM_KEYS & set(changed_keys)
        telemetry_before: tuple[str, str, str, str] | None = None
        if telemetry_subsystem_changed:
            telemetry_before = (
                get_telemetry_backend(),
                get_serial_port(),
                str(get_serial_baud()),
                get_mock_telemetry_type(),
            )
        save_settings(updates)

        reconfigured_keys: list[str] = []
        if mission_logic is not None:
            mission_keys = {"AI_MIN_CONFIDENCE", "AI_DUPLICATE_WINDOW_SEC"}
            if mission_keys & set(changed_keys):
                min_conf = (
                    get_ai_min_confidence() if "AI_MIN_CONFIDENCE" in updates else None
                )
                dup_win = (
                    get_ai_duplicate_window_sec()
                    if "AI_DUPLICATE_WINDOW_SEC" in updates
                    else None
                )
                mission_logic.reconfigure(
                    min_confidence=min_conf,
                    duplicate_window_sec=dup_win,
                )
                reconfigured_keys = [k for k in changed_keys if k in mission_keys]

        ai_reloaded_keys: list[str] = []
        ai_reload_error: Optional[str] = None
        ai_subsystem_changed = AI_SUBSYSTEM_KEYS & set(changed_keys)
        if reload_ai_fn is not None and ai_subsystem_changed:
            result = reload_ai_fn(provider_before)
            if isinstance(result, ReloadResult):
                if result.success:
                    ai_reloaded_keys = [
                        k for k in changed_keys if k in AI_SUBSYSTEM_KEYS
                    ]
                else:
                    ai_reload_error = result.error

        telemetry_reloaded_keys: list[str] = []
        telemetry_reload_error: Optional[str] = None
        if reload_telemetry_fn is not None and telemetry_subsystem_changed:
            backend = get_telemetry_backend()
            port = get_serial_port()
            valid, validation_err = validate_serial_config(backend, port)
            if not valid:
                telemetry_reload_error = validation_err
            else:
                telemetry_after = (
                    get_telemetry_backend(),
                    get_serial_port(),
                    str(get_serial_baud()),
                    get_mock_telemetry_type(),
                )
                if telemetry_before is not None and telemetry_before == telemetry_after:
                    pass
                else:
                    tel_result = await reload_telemetry_fn()
                    if isinstance(tel_result, TelemetryReconnectResult):
                        if tel_result.success:
                            telemetry_reloaded_keys = [
                                k for k in changed_keys if k in TELEMETRY_SUBSYSTEM_KEYS
                            ]
                        else:
                            telemetry_reload_error = tel_result.error

        live_keys = [k for k in changed_keys if SETTING_APPLY_MODES.get(k) == "live"]
        live_keys.extend(reconfigured_keys)
        live_keys.extend(ai_reloaded_keys)
        live_keys.extend(telemetry_reloaded_keys)
        reconnect_keys = [
            k
            for k in changed_keys
            if SETTING_APPLY_MODES.get(k) == "reconnect"
            and k not in reconfigured_keys
            and k not in ai_reloaded_keys
            and k not in telemetry_reloaded_keys
        ]
        restart_keys = [
            k
            for k in changed_keys
            if SETTING_APPLY_MODES.get(k) == "restart"
            and k not in telemetry_reloaded_keys
        ]

        restart_required = len(restart_keys) > 0
        reconnect_required = len(reconnect_keys) > 0

        if live_keys and not reconnect_required and not restart_required:
            message = "Settings saved. Changes apply immediately."
        elif ai_reload_error or telemetry_reload_error:
            errors = []
            if ai_reload_error:
                errors.append(f"AI reload failed: {ai_reload_error}")
            if telemetry_reload_error:
                errors.append(f"Telemetry reconnect failed: {telemetry_reload_error}")
            message = "Settings saved. " + "; ".join(errors)
            if live_keys:
                message += f" {len(live_keys)} other changes apply immediately."
        elif reconnect_required and not restart_required:
            message = "Settings saved. Some changes take effect after reconnect support is added."
        elif restart_required:
            parts = ["Settings saved."]
            if live_keys:
                parts.append(f"{len(live_keys)} apply immediately.")
            if ai_reload_error:
                parts.append(f"AI reload failed: {ai_reload_error}.")
            if telemetry_reload_error:
                parts.append(f"Telemetry reconnect failed: {telemetry_reload_error}.")
            if reconnect_required:
                parts.append(
                    f"{len(reconnect_keys)} take effect after reconnect support is added."
                )
            parts.append(f"{len(restart_keys)} require app restart.")
            message = " ".join(parts)
        else:
            message = "Settings saved."

        active_summary = build_active_summary()

        return {
            "ok": True,
            "message": message,
            "changed_keys": changed_keys,
            "live": live_keys,
            "reconnect": reconnect_keys,
            "restart": restart_keys,
            "restart_required": restart_required,
            "reconnect_required": reconnect_required,
            "active_telemetry_backend": get_telemetry_backend(),
            "active_ai_provider": get_local_llm_provider(),
            "active_summary": active_summary,
        }

    return router
