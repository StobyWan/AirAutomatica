"""AI HAT status and diagnostics routes."""

import logging
import shutil
import subprocess

from fastapi import APIRouter

from airautomatica.ai.hailo_detection import RPCAM_ASSETS_PATH, get_hailo_status
from airautomatica.config import get_ai_hat_enabled

logger = logging.getLogger(__name__)


def create_ai_router() -> APIRouter:
    """Create AI HAT status and diagnostics router."""
    router = APIRouter(prefix="/api/ai", tags=["ai"])

    @router.get("/status")
    def get_ai_status() -> dict:
        """Return AI HAT status. Capability, not health."""
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
        }

    @router.get("/diagnostics")
    def get_ai_diagnostics() -> dict:
        """Return detailed AI HAT diagnostics for troubleshooting."""
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
        }

    return router
