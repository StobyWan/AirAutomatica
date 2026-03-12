"""Shared API helpers."""

from airautomatica.config import (
    get_ai_hat_enabled,
    get_local_llm_model,
    get_local_llm_provider,
    get_serial_port,
    get_telemetry_backend,
)


def build_active_summary() -> str:
    """Build human-readable summary of active telemetry and AI backends."""
    backend = get_telemetry_backend()
    provider = get_local_llm_provider()
    if backend == "serial":
        active_telemetry = f"serial @ {get_serial_port()}"
    else:
        active_telemetry = backend
    if provider == "ollama":
        active_ai = f"ollama ({get_local_llm_model('ollama')})"
    else:
        active_ai = provider
    if get_ai_hat_enabled():
        active_ai = f"{active_ai} + AI HAT (perception)"
    return f"Telemetry: {active_telemetry} · AI: {active_ai}"
