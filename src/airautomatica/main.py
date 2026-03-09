"""Entry point: select telemetry and AI backends, run API and loops."""

import asyncio
import atexit
import logging

import uvicorn

from airautomatica.ai import AiHatAiService, LmStudioAiService, MockAiService, AiService
from airautomatica.api.server import create_app
from airautomatica.config import (
    get_ai_mode,
    get_ai_duplicate_window_sec,
    get_ai_min_confidence,
    get_aihat_device,
    get_aihat_model_name,
    get_api_host,
    get_api_port,
    get_lm_studio_base_url,
    get_lm_studio_model,
    get_lm_studio_timeout,
    get_serial_baud,
    get_serial_port,
    get_sqlite_db_path,
    get_telemetry_backend,
)
from airautomatica.db import init_db
from airautomatica.logging_config import setup_logging
from airautomatica.services.mission_logic import MissionLogic
from airautomatica.services.persistence import (
    PersistenceService,
    TelemetryLifecycleLogger,
    TelemetrySampler,
)
from airautomatica.services.state_store import StateStore
from airautomatica.telemetry import MockTelemetry, SerialMavlinkTelemetry, TelemetrySource

logger = logging.getLogger(__name__)


def _create_telemetry_source() -> TelemetrySource:
    """Create telemetry source based on TELEMETRY_BACKEND env var."""
    backend = get_telemetry_backend()
    if backend == "mock":
        return MockTelemetry()
    if backend == "serial":
        return SerialMavlinkTelemetry(
            port=get_serial_port(),
            baud=get_serial_baud(),
        )
    logger.warning("Unknown backend %r, defaulting to mock", backend)
    return MockTelemetry()


def _create_ai_service() -> AiService:
    """Create AI service based on AI_MODE env var."""
    mode = get_ai_mode()
    if mode == "mock":
        return MockAiService()
    if mode == "lmstudio":
        return LmStudioAiService(
            base_url=get_lm_studio_base_url(),
            model=get_lm_studio_model(),
            timeout_sec=get_lm_studio_timeout(),
        )
    if mode == "aihat":
        return AiHatAiService(
            model_name=get_aihat_model_name(),
            device=get_aihat_device(),
        )
    logger.warning("Unknown AI mode %r, defaulting to mock", mode)
    return MockAiService()


async def _telemetry_loop(
    store: StateStore,
    source: TelemetrySource,
    sampler: TelemetrySampler | None = None,
    lifecycle_logger: TelemetryLifecycleLogger | None = None,
) -> None:
    """Consume telemetry stream and update store."""
    async for state in source.stream():
        store.update(state)
        if sampler is not None:
            sampler.maybe_sample(state)
        if lifecycle_logger is not None:
            lifecycle_logger.maybe_log_transition(state)


def main() -> None:
    """Run API server, telemetry loop, and mission logic."""
    setup_logging()
    store = StateStore()
    source = _create_telemetry_source()
    ai_service = _create_ai_service()

    init_db(get_sqlite_db_path())

    persistence = PersistenceService()
    session_id = persistence.start_session(
        telemetry_backend=get_telemetry_backend(),
        ai_backend=get_ai_mode(),
    )
    if session_id is not None:
        logger.info("Session: id=%s", session_id)
    else:
        logger.warning("Session start failed; persistence disabled")
    sampler = TelemetrySampler(persistence, session_id, interval_sec=1.0)
    lifecycle_logger = TelemetryLifecycleLogger(persistence, session_id)

    def _end_session() -> None:
        if session_id is not None:
            persistence.end_session(session_id)

    atexit.register(_end_session)

    app = create_app(store, persistence=persistence, session_id=session_id)
    host = get_api_host()
    port = get_api_port()

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
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
        await asyncio.gather(
            server.serve(),
            _telemetry_loop(store, source, sampler, lifecycle_logger),
            mission_logic.run(),
        )

    logger.info(
        "Starting AIRAUTOMATICA (telemetry=%s ai=%s)",
        get_telemetry_backend(),
        get_ai_mode(),
    )
    if get_telemetry_backend() == "serial":
        logger.info("Serial telemetry: port=%s baud=%s", get_serial_port(), get_serial_baud())
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
