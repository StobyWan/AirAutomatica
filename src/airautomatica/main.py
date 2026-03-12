"""Entry point: select telemetry and AI backends, run API and loops."""

from airautomatica.settings import load_settings

load_settings()

import asyncio
import atexit
import logging
import os
import signal
import sys
from collections.abc import Coroutine
from typing import Any, Callable

import uvicorn

from airautomatica.ai import (
    AiHatAiService,
    AiService,
    ComposedAiService,
    MockAiService,
    OllamaAiService,
    OllamaTaskService,
)
from airautomatica.ai.ollama_readiness import wait_for_ollama_ready
from airautomatica.ai.scheduler import (
    AiInferenceScheduler,
    ScheduledOllamaAiService,
    ScheduledOllamaExecutor,
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
    get_camera_recording_mode,
    get_effective_ai_backend,
    get_local_llm_base_url,
    get_local_llm_model,
    get_local_llm_provider,
    get_local_llm_timeout,
    get_ollama_required,
    get_preprocessing_enabled,
    get_serial_baud,
    get_serial_port,
    get_session_auto_start_on_arm,
    get_sqlite_db_path,
    get_telemetry_backend,
)
from airautomatica.db import init_db
from airautomatica.logging_config import setup_logging
from airautomatica.realtime import DashboardPublisher, sio, wrap_app
from airautomatica.runtime.ai_subsystem import AiSubsystemHolder, ReloadResult
from airautomatica.runtime.telemetry_subsystem import (
    TelemetryController,
    TelemetryReconnectResult,
)
from airautomatica.services.camera_recording import (
    CameraRecordingService,
    RecordingAutoController,
)
from airautomatica.services.connection_state_store import ConnectionStateStore
from airautomatica.services.mission_logic import MissionLogic
from airautomatica.services.persistence import (
    PathRecorder,
    PersistenceService,
    TelemetryLifecycleLogger,
    TelemetrySampler,
)
from airautomatica.services.session_auto_controller import SessionAutoController
from airautomatica.services.state_store import StateStore
from airautomatica.telemetry import (
    MockTelemetry,
    SerialMavlinkTelemetry,
    TelemetrySource,
)
from airautomatica.telemetry.capabilities import CapabilityInfo
from airautomatica.telemetry.preprocessing import TelemetryPreprocessor

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


def _create_base_ai_service(
    ollama_transport: OllamaAiService | None = None,
    scheduler: AiInferenceScheduler | None = None,
) -> AiService:
    """Create base local LLM service (mock or ollama). AI HAT is composed separately."""
    provider = get_local_llm_provider()
    if provider == "mock":
        return MockAiService()
    if provider == "ollama":
        if ollama_transport is not None and scheduler is not None:
            return ScheduledOllamaAiService(ollama_transport, scheduler)
        return OllamaAiService(
            base_url=get_local_llm_base_url("ollama"),
            model=get_local_llm_model("ollama"),
            timeout_sec=get_local_llm_timeout(),
        )
    logger.warning("Unknown AI provider %r, defaulting to mock", provider)
    return MockAiService()


def _create_ai_service(
    ollama_transport: OllamaAiService | None = None,
    scheduler: AiInferenceScheduler | None = None,
) -> AiService:
    """Create composed AI service: base local LLM + optional AI HAT layer."""
    base = _create_base_ai_service(ollama_transport, scheduler)
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
    recording_auto_controller: RecordingAutoController | None = None,
    session_auto_controller: SessionAutoController | None = None,
    preprocessor: TelemetryPreprocessor | None = None,
) -> None:
    """Consume telemetry stream and update store."""
    async for state in source.stream():
        store.update(state)
        if preprocessor is not None:
            preprocessor.on_state(state)
        if sampler is not None:
            sampler.maybe_sample(state)
        if path_recorder is not None:
            path_recorder.maybe_record(state)
        if lifecycle_logger is not None:
            lifecycle_logger.maybe_log_transition(state)
        if recording_auto_controller is not None:
            recording_auto_controller.maybe_auto_record(state)
        if session_auto_controller is not None:
            session_auto_controller.maybe_auto_start_stop(state)


def _create_task_service(
    ollama_transport: OllamaAiService | None = None,
    scheduler: AiInferenceScheduler | None = None,
) -> OllamaTaskService:
    """Create OllamaTaskService for dashboard AI tasks (telemetry summary, etc.)."""
    provider = get_local_llm_provider()
    if provider == "ollama":
        if ollama_transport is not None and scheduler is not None:
            executor = ScheduledOllamaExecutor(ollama_transport, scheduler)
            logger.debug(
                "Task service: provider=%s executor=ScheduledOllamaExecutor (scheduled)",
                provider,
            )
            return OllamaTaskService(provider="ollama", ollama_service=executor)
        ollama = OllamaAiService(
            base_url=get_local_llm_base_url("ollama"),
            model=get_local_llm_model("ollama"),
            timeout_sec=get_local_llm_timeout(),
        )
        logger.debug(
            "Task service: provider=%s executor=OllamaAiService (direct)",
            provider,
        )
        return OllamaTaskService(provider="ollama", ollama_service=ollama)
    logger.debug("Task service: provider=%s executor=mock", provider)
    return OllamaTaskService(provider="mock", ollama_service=None)


def _reload_ai_subsystem(
    holder: AiSubsystemHolder,
    mission_logic: MissionLogic,
    scheduler: AiInferenceScheduler | None,
    provider_before: str,
) -> ReloadResult:
    """Recreate ai_service and task_service from current config and swap into holder.
    Returns failure if provider changed (requires restart) or creation fails."""
    provider_after = get_local_llm_provider()
    if provider_before != provider_after:
        logger.warning(
            "AI reload skipped: provider change %s -> %s requires app restart",
            provider_before,
            provider_after,
        )
        return ReloadResult(
            success=False,
            error="Provider change requires app restart",
            provider_before=provider_before,
            provider_after=provider_after,
        )
    if provider_after == "ollama" and scheduler is None:
        logger.warning(
            "AI reload skipped: switching to ollama requires app restart (no scheduler)"
        )
        return ReloadResult(
            success=False,
            error="Switching to Ollama requires app restart",
            provider_before=provider_before,
            provider_after=provider_after,
        )
    try:
        ollama_transport: OllamaAiService | None = None
        if provider_after == "ollama":
            ollama_transport = OllamaAiService(
                base_url=get_local_llm_base_url("ollama"),
                model=get_local_llm_model("ollama"),
                timeout_sec=get_local_llm_timeout(),
            )
        new_ai = _create_ai_service(ollama_transport, scheduler)
        new_task = _create_task_service(ollama_transport, scheduler)
        holder.swap(new_ai, new_task)
        mission_logic.set_ai_service(new_ai)
        logger.info("AI subsystem reloaded: provider=%s", provider_after)
        return ReloadResult(
            success=True,
            provider_before=provider_before,
            provider_after=provider_after,
        )
    except Exception as e:
        logger.exception("AI subsystem reload failed: %s", e)
        return ReloadResult(
            success=False,
            error=str(e),
            provider_before=provider_before,
            provider_after=provider_after,
        )


def main() -> None:
    """Run API server, telemetry loop, and mission logic."""
    setup_logging()
    store = StateStore()
    provider = get_local_llm_provider()
    ollama_transport: OllamaAiService | None = None
    scheduler: AiInferenceScheduler | None = None
    if provider == "ollama":
        ollama_transport = OllamaAiService(
            base_url=get_local_llm_base_url("ollama"),
            model=get_local_llm_model("ollama"),
            timeout_sec=get_local_llm_timeout(),
        )
        scheduler = AiInferenceScheduler()
    logger.debug(
        "Startup: provider=%s ollama_transport=%s scheduler=%s",
        provider,
        "created" if ollama_transport is not None else "none",
        "created" if scheduler is not None else "none",
    )
    ai_service = _create_ai_service(ollama_transport, scheduler)
    task_service = _create_task_service(ollama_transport, scheduler)

    init_db(get_sqlite_db_path())

    persistence = PersistenceService()
    connection_store = ConnectionStateStore()
    session_ref: list[int | None] = [None]
    source = _create_telemetry_source(store, persistence, session_ref)
    sampler = TelemetrySampler(persistence, session_ref, interval_sec=1.0)
    path_recorder = PathRecorder(persistence, session_ref, min_distance_m=5.0)
    lifecycle_logger = TelemetryLifecycleLogger(persistence, session_ref)

    camera_recording_service = CameraRecordingService()
    logger.info(
        "Recordings path: dir=%s cwd=%s HOME=%s AIRAUTOMATICA_RECORDINGS_DIR=%s",
        camera_recording_service.recordings_dir,
        os.getcwd(),
        os.environ.get("HOME", "<unset>"),
        "set" if os.environ.get("AIRAUTOMATICA_RECORDINGS_DIR") else "unset",
    )
    recording_auto_controller = RecordingAutoController(
        camera_recording_service,
        get_mode_fn=get_camera_recording_mode,
    )
    session_auto_controller = SessionAutoController(
        persistence,
        session_ref,
        connection_store,
        get_enabled_fn=get_session_auto_start_on_arm,
    )

    preprocessor: TelemetryPreprocessor | None = None
    if get_preprocessing_enabled():
        preprocessor = TelemetryPreprocessor()
        logger.debug("Telemetry preprocessing enabled")

    def _end_session() -> None:
        try:
            _shutdown_cleanup(persistence, session_ref, log_shutdown=False)
        except (KeyboardInterrupt, Exception):
            pass  # Avoid "Exception ignored in atexit callback" traceback

    atexit.register(_end_session)

    ai_holder = AiSubsystemHolder(ai_service, task_service)

    mission_logic = MissionLogic(
        store,
        ai_service=ai_service,
        persistence=persistence,
        session_ref=session_ref,
        min_confidence=get_ai_min_confidence(),
        duplicate_window_sec=get_ai_duplicate_window_sec(),
    )

    def _reload_fn(provider_before: str) -> ReloadResult:
        return _reload_ai_subsystem(
            ai_holder, mission_logic, scheduler, provider_before
        )

    def _create_telemetry_source_fn() -> TelemetrySource:
        return _create_telemetry_source(store, persistence, session_ref)

    def _start_telemetry_task(src: TelemetrySource) -> asyncio.Task[None]:
        return asyncio.create_task(
            _run_with_restart(
                _telemetry_loop,
                store,
                src,
                sampler,
                path_recorder,
                lifecycle_logger,
                recording_auto_controller,
                session_auto_controller,
                preprocessor,
                name="telemetry",
            )
        )

    telemetry_controller = TelemetryController(
        source=source,
        create_source_fn=_create_telemetry_source_fn,
        get_backend_fn=get_telemetry_backend,
        start_task_fn=_start_telemetry_task,
    )

    async def _reload_telemetry_fn() -> TelemetryReconnectResult:
        return await telemetry_controller.reconnect()

    app = create_app(
        store,
        connection_store=connection_store,
        session_ref=session_ref,
        persistence=persistence,
        ai_holder=ai_holder,
        camera_recording_service=camera_recording_service,
        preprocessor=preprocessor,
        mission_logic=mission_logic,
        reload_ai_fn=_reload_fn,
        reload_telemetry_fn=_reload_telemetry_fn,
    )
    asgi_app = wrap_app(app)
    host = get_api_host()
    port = get_api_port()

    publisher = DashboardPublisher(
        store,
        persistence,
        session_ref,
        get_effective_ai_backend(),
        get_telemetry_backend(),
        sio,
        interval_sec=1.0,
        camera_recording_service=camera_recording_service,
    )

    config = uvicorn.Config(asgi_app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    async def run_all() -> None:
        shutdown_event = asyncio.Event()

        if provider == "ollama":
            model = get_local_llm_model("ollama")
            result = await wait_for_ollama_ready(
                get_local_llm_base_url("ollama"),
                model=model,
                max_attempts=5,
                interval_sec=2.0,
                timeout_sec=3.0,
            )
            if result.ready:
                logger.info("Ollama ready with model %r", model)
            else:
                if result.reason == "unreachable":
                    logger.warning(
                        "Ollama not reachable at startup; proceeding without Ollama"
                    )
                elif result.reason == "model_missing":
                    logger.warning(
                        "Ollama is running but model %r is not installed; proceeding without Ollama",
                        model,
                    )
                elif result.reason == "http_error":
                    logger.warning(
                        "Ollama returned HTTP error at startup; proceeding without Ollama"
                    )
                else:
                    logger.warning(
                        "Ollama readiness failed after retries; AI features will run in degraded mode"
                    )
                if get_ollama_required():
                    logger.error(
                        "Ollama required but not ready: %s (%s)",
                        result.reason,
                        result.detail or "no detail",
                    )
                    sys.exit(1)

        def _on_signal(signum: int, frame) -> None:
            shutdown_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _on_signal)
            except (ValueError, OSError):
                pass

        server_task = asyncio.create_task(server.serve())
        scheduler_task: asyncio.Task[None] | None = None
        if scheduler is not None:
            scheduler_task = asyncio.create_task(scheduler.run())
        telemetry_task = telemetry_controller.start()
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
        camera_recording_service.stop_and_cleanup()

        all_tasks = [server_task, telemetry_task, mission_task, publisher_task]
        if scheduler_task is not None:
            all_tasks.append(scheduler_task)
        for t in all_tasks:
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
