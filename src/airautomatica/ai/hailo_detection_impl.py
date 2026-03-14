"""Hailo one-shot object detection implementation.

Uses hailo-apps when available: HailoInfer + extract_detections.
Frame capture via rpicam-still. Model: yolov6n_h8l.hef from hailo-models.

Verified imports (hailo-apps):
- hailo_apps.python.core.common.hailo_inference.HailoInfer
- hailo_apps.python.standalone_apps.object_detection.object_detection_post_process.extract_detections
- hailo_apps.python.core.common.toolbox.default_preprocess, get_labels
"""

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from airautomatica.ai.detection_models import (
    Detection,
    DetectionBBox,
    DetectionResult,
    DetectionState,
)
from airautomatica.config import get_ai_hat_detection_threshold

logger = logging.getLogger(__name__)

# Phase 1: single known model path (hailo-models package on Pi)
HEF_PATH_H8L = Path("/usr/share/hailo-models/yolov6n_h8l.hef")
CAPTURE_TIMEOUT_SEC = 20
INFERENCE_TIMEOUT_MS = 15000


def _hailo_apps_available() -> bool:
    """True if hailo-apps can be imported."""
    try:
        import hailo_apps.python.core.common.hailo_inference  # noqa: F401

        return True
    except ImportError:
        return False


def _capture_frame() -> tuple[bytes | None, str | None]:
    """Capture one frame via rpicam-still. Returns (jpeg_bytes, error)."""
    rpicam = shutil.which("rpicam-still")
    if not rpicam:
        return None, "rpicam-still not found"

    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            path = Path(f.name)
        result = subprocess.run(
            [
                rpicam,
                "-t",
                "1",
                "--immediate",
                "-n",
                "-o",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=CAPTURE_TIMEOUT_SEC,
        )
        if result.returncode != 0:
            err = result.stderr or result.stdout or "unknown"
            path.unlink(missing_ok=True)
            return None, f"rpicam-still failed: {err}"
        if not path.exists():
            return None, "rpicam-still did not produce output"
        data = path.read_bytes()
        path.unlink(missing_ok=True)
        return data, None
    except subprocess.TimeoutExpired:
        path.unlink(missing_ok=True)
        return None, "camera capture timed out"
    except Exception as e:
        if "path" in dir() and path.exists():
            path.unlink(missing_ok=True)
        return None, f"camera capture failed: {e}"


def run_inference_on_image_bytes(
    image_bytes: bytes,
    hef_path: Path | None = None,
) -> tuple[DetectionResult, bool]:
    """Run Hailo inference on image bytes (JPEG/PNG). Returns (result, success).

    Public helper for recording-time ingestion and one-shot detection.
    """
    path = hef_path or HEF_PATH_H8L
    return _run_inference_on_image(image_bytes, path)


def _run_inference_on_image(
    image_bytes: bytes,
    hef_path: Path,
) -> tuple[DetectionResult, bool]:
    """Run Hailo inference. Returns (result, success). Internal implementation."""
    if not _hailo_apps_available():
        return (
            DetectionResult(
                backend="hailo",
                model="yolov6n",
                state="unavailable",
                structured_output_supported=False,
                detections=[],
                frame_width=None,
                frame_height=None,
                inference_time_ms=None,
                errors=[
                    "hailo-apps not installed; clone hailo-apps and run packaging/linux/install-ai-hat-apps.sh (Pi only)"
                ],
            ),
            False,
        )

    if not hef_path.exists():
        return (
            DetectionResult(
                backend="hailo",
                model="yolov6n",
                state="unavailable",
                structured_output_supported=False,
                detections=[],
                frame_width=None,
                frame_height=None,
                inference_time_ms=None,
                errors=[f"HEF not found: {hef_path}"],
            ),
            False,
        )

    try:
        import cv2
        import numpy as np
        from hailo_apps.python.core.common.hailo_inference import HailoInfer
        from hailo_apps.python.core.common.toolbox import default_preprocess, get_labels
        from hailo_apps.python.standalone_apps.object_detection.object_detection_post_process import (
            extract_detections,
        )
    except ImportError as e:
        return (
            DetectionResult(
                backend="hailo",
                model="yolov6n",
                state="unavailable",
                structured_output_supported=False,
                detections=[],
                frame_width=None,
                frame_height=None,
                inference_time_ms=None,
                errors=[f"hailo-apps import failed: {e}"],
            ),
            False,
        )

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return (
                DetectionResult(
                    backend="hailo",
                    model="yolov6n",
                    state="error",
                    structured_output_supported=True,
                    detections=[],
                    frame_width=None,
                    frame_height=None,
                    inference_time_ms=None,
                    errors=["failed to decode captured image"],
                ),
                False,
            )
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_h, img_w = frame_rgb.shape[:2]

        infer = HailoInfer(str(hef_path), batch_size=1)
        try:
            model_h, model_w = infer.get_input_shape()[:2]
            preprocessed = default_preprocess(frame_rgb, model_w, model_h)
            preprocessed_batch = [preprocessed]

            output_queue: list = []
            output_holder: dict = {"result": None, "exception": None}

            def _callback(completion_info, bindings_list, **kwargs):
                if completion_info.exception:
                    output_holder["exception"] = completion_info.exception
                    return
                bindings = bindings_list[0]
                if (
                    hasattr(bindings, "_output_names")
                    and len(bindings._output_names) == 1
                ):
                    out = bindings.output().get_buffer()
                else:
                    out = {
                        n: np.expand_dims(bindings.output(n).get_buffer(), axis=0)
                        for n in bindings._output_names
                    }
                output_holder["result"] = out

            t0 = time.perf_counter()
            job = infer.run(preprocessed_batch, _callback)
            job.wait(INFERENCE_TIMEOUT_MS)
            inference_time_ms = (time.perf_counter() - t0) * 1000
        finally:
            infer.close()

        if output_holder["exception"]:
            return (
                DetectionResult(
                    backend="hailo",
                    model="yolov6n",
                    state="error",
                    structured_output_supported=True,
                    detections=[],
                    frame_width=img_w,
                    frame_height=img_h,
                    inference_time_ms=inference_time_ms,
                    errors=[str(output_holder["exception"])],
                ),
                False,
            )

        raw_output = output_holder["result"]
        if raw_output is None:
            return (
                DetectionResult(
                    backend="hailo",
                    model="yolov6n",
                    state="error",
                    structured_output_supported=True,
                    detections=[],
                    frame_width=img_w,
                    frame_height=img_h,
                    inference_time_ms=inference_time_ms,
                    errors=["inference produced no output"],
                ),
                False,
            )

        config_data = {
            "visualization_params": {
                "score_thres": 0.25,
                "max_boxes_to_draw": 100,
            }
        }
        labels = get_labels(None)
        try:
            detections_dict = extract_detections(frame_rgb, raw_output, config_data)
        except Exception as ext_err:
            logger.exception("extract_detections failed")
            return (
                DetectionResult(
                    backend="hailo",
                    model="yolov6n",
                    state="error",
                    structured_output_supported=True,
                    detections=[],
                    frame_width=img_w,
                    frame_height=img_h,
                    inference_time_ms=inference_time_ms,
                    errors=[f"postprocess failed: {ext_err}"],
                ),
                False,
            )
    except Exception as e:
        logger.exception("Hailo inference failed")
        return (
            DetectionResult(
                backend="hailo",
                model="yolov6n",
                state="error",
                structured_output_supported=True,
                detections=[],
                frame_width=None,
                frame_height=None,
                inference_time_ms=None,
                errors=[str(e)],
            ),
            False,
        )

    boxes = detections_dict.get("detection_boxes", [])
    scores = detections_dict.get("detection_scores", [])
    classes = detections_dict.get("detection_classes", [])
    num_det = detections_dict.get("num_detections", 0)

    threshold = get_ai_hat_detection_threshold()
    detections: list[Detection] = []
    for i in range(num_det):
        box = boxes[i]
        score = float(scores[i])
        if score < threshold:
            continue
        class_id = int(classes[i])
        label = labels[class_id] if class_id < len(labels) else f"class_{class_id}"
        xmin, ymin, xmax, ymax = box
        w_px = xmax - xmin
        h_px = ymax - ymin
        x_norm = xmin / img_w if img_w > 0 else 0
        y_norm = ymin / img_h if img_h > 0 else 0
        w_norm = w_px / img_w if img_w > 0 else 0
        h_norm = h_px / img_h if img_h > 0 else 0
        detections.append(
            Detection(
                label=label,
                confidence=score,
                bbox=DetectionBBox(x=x_norm, y=y_norm, width=w_norm, height=h_norm),
                timestamp=None,
                source="camera",
            )
        )

    state: DetectionState = "ready" if detections else "no_detections"
    return (
        DetectionResult(
            backend="hailo",
            model="yolov6n",
            state=state,
            structured_output_supported=True,
            detections=detections,
            frame_width=img_w,
            frame_height=img_h,
            inference_time_ms=inference_time_ms,
            errors=[],
        ),
        True,
    )


def run_one_shot_detection() -> DetectionResult:
    """Capture one frame, run inference, return structured result. Never raises."""
    frame_data, capture_err = _capture_frame()
    if capture_err or frame_data is None:
        return DetectionResult(
            backend="hailo",
            model="yolov6n",
            state="error",
            structured_output_supported=_hailo_apps_available(),
            detections=[],
            frame_width=None,
            frame_height=None,
            inference_time_ms=None,
            errors=[capture_err] if capture_err else ["no frame data"],
        )

    result, _ = run_inference_on_image_bytes(frame_data)
    return result
