"""AI HAT status and diagnostics routes."""

import logging
import shutil
import subprocess
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter

from airautomatica.ai.event_normalizer import (
    normalize_detections_to_events,
)
from airautomatica.ai.models import AiResult

if TYPE_CHECKING:
    from airautomatica.services.persistence import PersistenceService
from airautomatica.ai.hailo_detection import RPCAM_ASSETS_PATH, get_hailo_status
from airautomatica.ai.hailo_detection_impl import _hailo_apps_available
from airautomatica.ai.providers.hailo_provider import HailoAiHatProvider
from airautomatica.config import (
    get_ai_hat_camera_pipeline_enabled,
    get_ai_hat_detection_threshold,
    get_ai_hat_enabled,
    get_ai_hat_object_detection_enabled,
)
from airautomatica.services.ai_detection_store import AiDetectionStore

if TYPE_CHECKING:
    from airautomatica.services.ai_detection_store import AiDetectionStore
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)


def create_ai_router(
    ai_detection_store: Optional[AiDetectionStore] = None,
    persistence: Optional["PersistenceService"] = None,
    session_ref: Optional[list[int | None]] = None,
) -> APIRouter:
    """Create AI HAT status and diagnostics router."""
    router = APIRouter(prefix="/api/ai", tags=["ai"])

    @router.get("/status")
    def get_ai_status() -> dict:
        """AI HAT capability and current config/readiness. Not health—use /health for that."""
        enabled = get_ai_hat_enabled()
        result = get_hailo_status()

        if not enabled:
            return {
                "enabled": False,
                "detected": result.available,
                "state": "disabled",
                "backend": "none",
                "device_class": result.device_class,
                "board_name": result.board_name,
                "driver_ready": result.driver_ready,
                "camera_ai_postprocess_available": result.camera_ai_postprocess_available,
                "errors": [],
                "detection_threshold": get_ai_hat_detection_threshold(),
            }

        return {
            "enabled": True,
            "detected": result.available,
            "state": result.state,
            "backend": "hailo",
            "device_class": result.device_class,
            "board_name": result.board_name,
            "driver_ready": result.driver_ready,
            "camera_ai_postprocess_available": result.camera_ai_postprocess_available,
            "errors": result.errors,
            "detection_threshold": get_ai_hat_detection_threshold(),
        }

    @router.get("/diagnostics")
    def get_ai_diagnostics() -> dict:
        """Deep AI HAT troubleshooting: lspci, hailortcli, paths, object_detection block."""
        result = get_hailo_status()

        hailortcli_path = shutil.which("hailortcli")
        lspci_output: str | None = None
        lspci_ok = False
        try:
            lspci_result = subprocess.run(
                ["lspci"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if lspci_result.returncode == 0:
                lspci_output = lspci_result.stdout or ""
                lspci_ok = "Hailo" in lspci_output
        except Exception as e:
            lspci_output = f"Error: {e}"

        identify_output: str | None = None
        if hailortcli_path:
            try:
                ident_result = subprocess.run(
                    [hailortcli_path, "fw-control", "identify"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                identify_output = (
                    ident_result.stdout or ident_result.stderr or "(empty)"
                )
            except Exception as e:
                identify_output = f"Error: {e}"

        rpicam_assets_exist = RPCAM_ASSETS_PATH.exists()
        rpicam_still_path = shutil.which("rpicam-still")
        hailo_apps_avail = _hailo_apps_available()
        detection_enabled = get_ai_hat_object_detection_enabled()
        camera_pipeline_enabled = get_ai_hat_camera_pipeline_enabled()

        return {
            "hailortcli_exists": hailortcli_path is not None,
            "hailortcli_path": hailortcli_path,
            "lspci_hailo_detected": lspci_ok,
            "lspci_output": lspci_output[:500] if lspci_output else None,
            "identify_output": identify_output[:1000] if identify_output else None,
            "rpicam_assets_path": str(RPCAM_ASSETS_PATH),
            "rpicam_assets_exist": rpicam_assets_exist,
            "status": {
                "available": result.available,
                "state": result.state,
                "device_class": result.device_class,
                "board_name": result.board_name,
                "driver_ready": result.driver_ready,
                "camera_ai_postprocess_available": result.camera_ai_postprocess_available,
                "errors": result.errors,
            },
            "enabled": get_ai_hat_enabled(),
            "object_detection": {
                "detection_enabled": detection_enabled,
                "structured_detection_supported": hailo_apps_avail,
                "camera_capture_available": rpicam_still_path is not None,
                "selected_detection_path": "hailo-apps" if hailo_apps_avail else "none",
                "detection_threshold": get_ai_hat_detection_threshold(),
                "blocked_by_config": not detection_enabled
                or not camera_pipeline_enabled,
                "blocked_by_missing_runtime": not hailo_apps_avail,
                "blocked_by_missing_camera": rpicam_still_path is None,
            },
        }

    @router.post("/detect")
    def post_ai_detect() -> dict:
        """Execute one-shot detection: capture frame, run Hailo inference, return structured detections and normalized events."""
        provider = HailoAiHatProvider()
        result = provider.run_object_detection()
        sid = session_ref[0] if session_ref else None
        if ai_detection_store is not None:
            ai_detection_store.set_last_detection(
                result, source="camera", session_id=sid
            )
        out = result.to_dict()
        events = normalize_detections_to_events(result.detections)
        out["events"] = [e.to_dict() for e in events]
        # Session-linking: persist each detection when session is active
        if (
            persistence is not None
            and sid is not None
            and result.state == "ready"
            and result.detections
        ):
            now = datetime.now(timezone.utc)
            for det in result.detections:
                bbox = (
                    (det.bbox.x, det.bbox.y, det.bbox.width, det.bbox.height)
                    if det.bbox
                    else None
                )
                ai_result = AiResult(
                    label=det.label,
                    confidence=det.confidence,
                    summary=f"{det.label} detected (AI HAT one-shot)",
                    source_backend="aihat",
                    timestamp=now,
                    bbox=bbox,
                    metadata={"one_shot": True},
                )
                persistence.insert_detection(
                    session_id=sid,
                    result=ai_result,
                    lat=None,
                    lon=None,
                    rel_alt_m=None,
                )
        # person_detected hook: append system event
        if persistence is not None and session_ref is not None:
            person_ev = next(
                (e for e in events if e.event_type == "person_detected"),
                None,
            )
            if person_ev is not None:
                sid_val = session_ref[0]
                if sid_val is not None:
                    persistence.insert_system_event(
                        session_id=sid_val,
                        level="info",
                        event_type="person_detected",
                        message="Person detected (AI HAT one-shot)",
                        metadata={
                            "confidence": person_ev.confidence,
                            "count": person_ev.count,
                            "label": person_ev.label,
                        },
                    )
        return out

    @router.get("/last-detection")
    def get_last_detection() -> dict:
        """Cached result of the most recent successful one-shot detection. Empty when none cached."""
        if ai_detection_store is None:
            return {"cached": False, "result": None, "timestamp": None}
        cached = ai_detection_store.get_last_detection()
        if cached is None:
            return {"cached": False, "result": None, "timestamp": None}
        result_dict = cached.result.to_dict()
        events = normalize_detections_to_events(cached.result.detections)
        result_dict["events"] = [e.to_dict() for e in events]
        return {
            "cached": True,
            "result": result_dict,
            "timestamp": cached.timestamp.isoformat(),
            "summary": cached.summary,
            "source": cached.source,
            "session_id": cached.session_id,
        }

    return router
