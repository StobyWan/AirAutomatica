"""Entry point: select telemetry and AI backends, run API and loops."""

from airautomatica.settings import load_settings

load_settings()

import asyncio
import atexit
import logging
import signal
import sys
from collections.abc import Coroutine
from typing import Any, Callable

import uvicorn

from airautomatica.ai import (
    AiHatAiService,
    AiService,
    ComposedAiService,
    LmStudioAiService,
    MockAiService,
    OllamaAiService,
)
from airautomatica.api.server import create_app
from airautomatica.config import (
    get_ai_duplicate_window_sec,
    get_ai_hat_enabled,
    get_ai_min_confidence,
    get_aihat_device,
    get_aihat_model_name,
    get_api_host,
    get_api_port,
    get_effective_ai_backend,
    get_lm_studio_base_url,
    get_lm_studio_model,
    get_lm_studio_timeout,
    get_local_llm_base_url,
    get_local_llm_model,
    get_local_llm_provider,
    get_local_llm_timeout,
    get_serial_baud,
    get_serial_port,
    get_sqlite_db_path,
    get_telemetry_backend,
)
from airautomatica.db import init_db
from airautomatica.logging_config import setup_logging
from airautomatica.realtime import DashboardPublisher, sio, wrap_app
from airautomatica.services.mission_logic import MissionLogic
from airautomatica.services.persistence import (
    PathRecorder,
    PersistenceService,
    TelemetryLifecycleLogger,
    TelemetrySampler,
)
from airautomatica.services.state_store import StateStore
from airautomatica.telemetry import (
    MockTelemetry,
    SerialMavlinkTelemetry,
    TelemetrySource,
)
from airautomatica.telemetry.capabilities import CapabilityInfo

logger = logging.getLogger(__name__)


def _shutdown_cleanup(
    persistence: PersistenceService,
    session_ref: list[int | None],
    log_shutdown: bool = True,
) -> None:
    """End current session and optionally log app_shutdown. Idempotent."""
    if log_shutdown:
        logger.info("Shutdown requested")
    sid = session_ref[0]
    if sid is not None:
        persistence.insert_system_event(
            session_id=sid,
            level="info",
            event_type="app_shutdown",
            message="Application shutdown",
        )
        persistence.end_session(sid)
        session_ref[0] = None


def _create_telemetry_source(
    store: StateStore,
    persistence: PersistenceService | None = None,
    session_ref: list[int | None] | None = None,
) -> TelemetrySource:
    """Create telemetry source based on TELEMETRY_BACKEND env var."""

    def _capability_callback(info: CapabilityInfo) -> None:
        store.set_capabilities(info)
        sid = session_ref[0] if session_ref else None
        if persistence is not None and sid is not None:
            persistence.insert_system_event(
                session_id=sid,
                level="info",
                event_type="capability_profile_set",
                message=f"Capability profile: {info.firmware_name} ({info.profile_id})",
                metadata={
                    "firmware_name": info.firmware_name,
                    "profile_id": info.profile_id,
                    "downgrade_reasons": list(info.downgrade_reasons),
                },
            )

    backend = get_telemetry_backend()
    if backend == "mock":
        return MockTelemetry()
    if backend == "serial":
        return SerialMavlinkTelemetry(
            port=get_serial_port(),
            baud=get_serial_baud(),
            capability_callback=_capability_callback,
        )
    logger.warning("Unknown backend %r, defaulting to mock", backend)
    return MockTelemetry()


def _create_base_ai_service() -> AiService:
    """Create base local LLM service (mock or ollama). AI HAT is composed separately."""
    provider = get_local_llm_provider()
    if provider == "mock":
        return MockAiService()
    if provider == "ollama":
        return OllamaAiService(
            base_url=get_local_llm_base_url("ollama"),
            model=get_local_llm_model("ollama"),
            timeout_sec=get_local_llm_timeout(),
        )
    if provider == "lmstudio":
        logger.warning(
            "LmStudioAiService is deprecated; prefer LOCAL_LLM_PROVIDER=ollama"
        )
        return LmStudioAiService(
            base_url=get_lm_studio_base_url(),
            model=get_lm_studio_model(),
            timeout_sec=get_lm_studio_timeout(),
        )
    logger.warning("Unknown AI provider %r, defaulting to mock", provider)
    return MockAiService()


def _create_ai_service() -> AiService:
    """Create composed AI service: base local LLM + optional AI HAT layer."""
    base = _create_base_ai_service()
    aihat: AiService | None = None
    if get_ai_hat_enabled():
        aihat = AiHatAiService(
            model_name=get_aihat_model_name(),
            device=get_aihat_device(),
        )
        logger.info(
            "AI HAT enabled alongside %s",
            get_local_llm_provider(),
        )
    if aihat is not None:
        return ComposedAiService(base_ai_service=base, aihat_service=aihat)
    return base


async def _run_with_restart(
    coro_fn: Callable[..., Coroutine[Any, Any, None]],
    *args: Any,
    name: str = "task",
    restart_delay_sec: float = 1.0,
    **kwargs: Any,
) -> None:
    """Run coroutine in a loop; on exception, log and restart after delay."""
    while True:
        try:
            await coro_fn(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(
                "%s failed, restarting in %.1fs: %s",
                name,
                restart_delay_sec,
                e,
            )
            await asyncio.sleep(restart_delay_sec)


async def _telemetry_loop(
    store: StateStore,
    source: TelemetrySource,
    sampler: TelemetrySampler | None = None,
    path_recorder: PathRecorder | None = None,
    lifecycle_logger: TelemetryLifecycleLogger | None = None,
) -> None:
    """Consume telemetry stream and update store."""
    async for state in source.stream():
        store.update(state)
        if sampler is not None:
            sampler.maybe_sample(state)
        if path_recorder is not None:
            path_recorder.maybe_record(state)
        if lifecycle_logger is not None:
            lifecycle_logger.maybe_log_transition(state)


def main() -> None:
    """Run API server, telemetry loop, and mission logic."""
    setup_logging()
    store = StateStore()
    ai_service = _create_ai_service()

    init_db(get_sqlite_db_path())

    persistence = PersistenceService()
    session_id = persistence.start_session(
        telemetry_backend=get_telemetry_backend(),
        ai_backend=get_effective_ai_backend(),
    )
    session_ref: list[int | None] = [session_id]
    source = _create_telemetry_source(store, persistence, session_ref)
    if session_id is not None:
        logger.info("Session: id=%s", session_id)
    else:
        logger.warning("Session start failed; persistence disabled")
    sampler = TelemetrySampler(persistence, session_id, interval_sec=1.0)
    path_recorder = PathRecorder(persistence, session_id, min_distance_m=5.0)
    lifecycle_logger = TelemetryLifecycleLogger(persistence, session_id)

    def _end_session() -> None:
        try:
            _shutdown_cleanup(persistence, session_ref, log_shutdown=False)
        except (KeyboardInterrupt, Exception):
            pass  # Avoid "Exception ignored in atexit callback" traceback

    atexit.register(_end_session)

    app = create_app(store, persistence=persistence, session_id=session_id)
    asgi_app = wrap_app(app)
    host = get_api_host()
    port = get_api_port()

    publisher = DashboardPublisher(
        store,
        persistence,
        session_id,
        get_effective_ai_backend(),
        get_telemetry_backend(),
        sio,
        interval_sec=1.0,
    )

    config = uvicorn.Config(asgi_app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    mission_logic = MissionLogic(
        store,
        ai_service=ai_service,
        persistence=persistence,
        session_id=session_id,
        min_confidence=get_ai_min_confidence(),
        duplicate_window_sec=get_ai_duplicate_window_sec(),
    )

    async def run_all() -> None:
        shutdown_event = asyncio.Event()

        def _on_signal(signum: int, frame) -> None:
            shutdown_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _on_signal)
            except (ValueError, OSError):
                pass

        server_task = asyncio.create_task(server.serve())
        telemetry_task = asyncio.create_task(
            _run_with_restart(
                _telemetry_loop,
                store,
                source,
                sampler,
                path_recorder,
                lifecycle_logger,
                name="telemetry",
            )
        )
        mission_task = asyncio.create_task(
            _run_with_restart(mission_logic.run, name="mission")
        )
        publisher_task = asyncio.create_task(publisher.run())
        shutdown_waiter = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [server_task, shutdown_waiter],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

        _shutdown_cleanup(persistence, session_ref)

        for t in (server_task, telemetry_task, mission_task, publisher_task):
            if not t.done():
                t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception("Task cleanup: %s", e)

    logger.info(
        "Starting AIRAUTOMATICA (telemetry=%s ai=%s)",
        get_telemetry_backend(),
        get_effective_ai_backend(),
    )
    if get_telemetry_backend() == "serial":
        logger.info(
            "Serial telemetry: port=%s baud=%s", get_serial_port(), get_serial_baud()
        )
    asyncio.run(run_all())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
