"""Tests for recording AI ingest (frame extraction + inference + persistence)."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from airautomatica.ai.detection_models import Detection, DetectionBBox, DetectionResult
from airautomatica.services.recording_ai_ingest import (
    RecordingAiIngest,
    _extract_latest_frame,
)


def test_extract_latest_frame_returns_none_when_file_missing(tmp_path: Path) -> None:
    """File not found returns None."""
    out = tmp_path / "missing.mp4"
    assert not out.exists()
    assert _extract_latest_frame(out) is None


def test_extract_latest_frame_returns_none_when_ffmpeg_unavailable(
    tmp_path: Path,
) -> None:
    """When ffmpeg is not found, returns None."""
    out = tmp_path / "rec.mp4"
    out.write_bytes(b"fake")
    with patch(
        "airautomatica.services.recording_ai_ingest.shutil.which", return_value=None
    ):
        assert _extract_latest_frame(out) is None


def test_extract_latest_frame_returns_bytes_when_ffmpeg_succeeds(
    tmp_path: Path,
) -> None:
    """When ffmpeg succeeds, returns frame bytes."""
    out = tmp_path / "rec.mp4"
    out.write_bytes(b"fake video")
    fake_frame = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    with patch(
        "airautomatica.services.recording_ai_ingest.shutil.which",
        return_value="/usr/bin/ffmpeg",
    ):
        with patch(
            "airautomatica.services.recording_ai_ingest.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=fake_frame),
        ):
            result = _extract_latest_frame(out)
    assert result == fake_frame


def test_extract_latest_frame_returns_none_when_ffmpeg_fails(tmp_path: Path) -> None:
    """When ffmpeg returns non-zero or empty stdout, returns None."""
    out = tmp_path / "rec.mp4"
    out.write_bytes(b"fake")
    with patch(
        "airautomatica.services.recording_ai_ingest.shutil.which",
        return_value="/usr/bin/ffmpeg",
    ):
        with patch(
            "airautomatica.services.recording_ai_ingest.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=b""),
        ):
            assert _extract_latest_frame(out) is None
        with patch(
            "airautomatica.services.recording_ai_ingest.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=b""),
        ):
            assert _extract_latest_frame(out) is None


def test_persist_detections_calls_insert_with_correct_source_backend() -> None:
    """Persisted detections use source_backend=ai_hat_recording and metadata.recording."""
    persistence = MagicMock()
    get_session_id = lambda: 42
    output_path = Path("/tmp/rec.mp4")
    ingest = RecordingAiIngest(
        output_path=output_path,
        get_session_id=get_session_id,
        persistence=persistence,
        interval_sec=5.0,
        startup_delay_sec=0.0,
    )
    result = DetectionResult(
        backend="hailo",
        model="yolov6n",
        state="ready",
        structured_output_supported=True,
        detections=[
            Detection(
                label="person",
                confidence=0.85,
                bbox=DetectionBBox(0.1, 0.2, 0.3, 0.4),
            ),
        ],
        frame_width=640,
        frame_height=480,
        inference_time_ms=25.0,
        errors=[],
    )
    ingest._persist_detections(42, result)
    persistence.insert_detection.assert_called_once()
    kwargs = persistence.insert_detection.call_args.kwargs
    assert kwargs["session_id"] == 42
    ai_result = kwargs["result"]
    assert ai_result.label == "person"
    assert ai_result.confidence == 0.85
    assert ai_result.source_backend == "ai_hat_recording"
    assert ai_result.metadata == {"recording": True}
    assert kwargs["lat"] is None
    assert kwargs["lon"] is None
    assert kwargs["rel_alt_m"] is None


def test_persist_detections_deduplicates_same_label_within_window() -> None:
    """Same label within 30s is persisted once."""
    persistence = MagicMock()
    ingest = RecordingAiIngest(
        output_path=Path("/tmp/rec.mp4"),
        get_session_id=lambda: 1,
        persistence=persistence,
        interval_sec=5.0,
        startup_delay_sec=0.0,
    )
    result = DetectionResult(
        backend="hailo",
        model="yolov6n",
        state="ready",
        structured_output_supported=True,
        detections=[
            Detection(
                label="car",
                confidence=0.9,
                bbox=DetectionBBox(0.0, 0.0, 0.2, 0.2),
            ),
        ],
        frame_width=640,
        frame_height=480,
        inference_time_ms=20.0,
        errors=[],
    )
    ingest._persist_detections(1, result)
    ingest._persist_detections(1, result)
    assert persistence.insert_detection.call_count == 1


def test_persist_detections_persists_distinct_labels() -> None:
    """Different labels are both persisted."""
    persistence = MagicMock()
    ingest = RecordingAiIngest(
        output_path=Path("/tmp/rec.mp4"),
        get_session_id=lambda: 1,
        persistence=persistence,
        interval_sec=5.0,
        startup_delay_sec=0.0,
    )
    for label in ("person", "car"):
        result = DetectionResult(
            backend="hailo",
            model="yolov6n",
            state="ready",
            structured_output_supported=True,
            detections=[
                Detection(
                    label=label,
                    confidence=0.8,
                    bbox=DetectionBBox(0.0, 0.0, 0.1, 0.1),
                ),
            ],
            frame_width=640,
            frame_height=480,
            inference_time_ms=20.0,
            errors=[],
        )
        ingest._persist_detections(1, result)
    assert persistence.insert_detection.call_count == 2


def test_tick_skips_persist_when_persistence_none(tmp_path: Path) -> None:
    """When persistence is None, _tick does not persist."""
    out = tmp_path / "rec.mp4"
    out.write_bytes(b"fake")
    ingest = RecordingAiIngest(
        output_path=out,
        get_session_id=lambda: 1,
        persistence=None,
        interval_sec=5.0,
        startup_delay_sec=0.0,
    )
    with patch(
        "airautomatica.services.recording_ai_ingest.shutil.which",
        return_value="/usr/bin/ffmpeg",
    ):
        with patch(
            "airautomatica.services.recording_ai_ingest.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=b"\xff\xd8"),
        ):
            with patch(
                "airautomatica.services.recording_ai_ingest.run_inference_on_image_bytes",
                return_value=(
                    DetectionResult(
                        backend="hailo",
                        model="yolov6n",
                        state="ready",
                        structured_output_supported=True,
                        detections=[
                            Detection(
                                label="person",
                                confidence=0.9,
                                bbox=DetectionBBox(0, 0, 0.1, 0.1),
                            ),
                        ],
                        frame_width=640,
                        frame_height=480,
                        inference_time_ms=20.0,
                        errors=[],
                    ),
                    True,
                ),
            ):
                ingest._tick()
    # No persistence to call; no crash


def test_tick_skips_when_frame_not_ready(tmp_path: Path) -> None:
    """When ffmpeg returns None (file not ready), _tick does not persist."""
    out = tmp_path / "rec.mp4"
    out.write_bytes(b"x")
    persistence = MagicMock()
    ingest = RecordingAiIngest(
        output_path=out,
        get_session_id=lambda: 1,
        persistence=persistence,
        interval_sec=5.0,
        startup_delay_sec=0.0,
    )
    with patch(
        "airautomatica.services.recording_ai_ingest.shutil.which",
        return_value="/usr/bin/ffmpeg",
    ):
        with patch(
            "airautomatica.services.recording_ai_ingest.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=b""),
        ):
            ingest._tick()
    persistence.insert_detection.assert_not_called()


def test_tick_skips_when_inference_fails(tmp_path: Path) -> None:
    """When inference fails or state != ready, _tick does not persist."""
    out = tmp_path / "rec.mp4"
    out.write_bytes(b"x")
    persistence = MagicMock()
    ingest = RecordingAiIngest(
        output_path=out,
        get_session_id=lambda: 1,
        persistence=persistence,
        interval_sec=5.0,
        startup_delay_sec=0.0,
    )
    with patch(
        "airautomatica.services.recording_ai_ingest.shutil.which",
        return_value="/usr/bin/ffmpeg",
    ):
        with patch(
            "airautomatica.services.recording_ai_ingest.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=b"\xff\xd8"),
        ):
            with patch(
                "airautomatica.services.recording_ai_ingest.run_inference_on_image_bytes",
                return_value=(
                    DetectionResult(
                        backend="hailo",
                        model="yolov6n",
                        state="error",
                        structured_output_supported=True,
                        detections=[],
                        frame_width=640,
                        frame_height=480,
                        inference_time_ms=0.0,
                        errors=["inference failed"],
                    ),
                    False,
                ),
            ):
                ingest._tick()
    persistence.insert_detection.assert_not_called()


def test_tick_persists_when_all_ready(tmp_path: Path) -> None:
    """When frame ready and inference succeeds, detections are persisted."""
    out = tmp_path / "rec.mp4"
    out.write_bytes(b"x")
    persistence = MagicMock()
    ingest = RecordingAiIngest(
        output_path=out,
        get_session_id=lambda: 99,
        persistence=persistence,
        interval_sec=5.0,
        startup_delay_sec=0.0,
    )
    with patch(
        "airautomatica.services.recording_ai_ingest.shutil.which",
        return_value="/usr/bin/ffmpeg",
    ):
        with patch(
            "airautomatica.services.recording_ai_ingest.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=b"\xff\xd8"),
        ):
            with patch(
                "airautomatica.services.recording_ai_ingest.run_inference_on_image_bytes",
                return_value=(
                    DetectionResult(
                        backend="hailo",
                        model="yolov6n",
                        state="ready",
                        structured_output_supported=True,
                        detections=[
                            Detection(
                                label="person",
                                confidence=0.92,
                                bbox=DetectionBBox(0.1, 0.2, 0.3, 0.4),
                            ),
                        ],
                        frame_width=640,
                        frame_height=480,
                        inference_time_ms=22.0,
                        errors=[],
                    ),
                    True,
                ),
            ):
                ingest._tick()
    persistence.insert_detection.assert_called_once()
    ai_result = persistence.insert_detection.call_args.kwargs["result"]
    assert ai_result.source_backend == "ai_hat_recording"
    assert ai_result.label == "person"
    assert ai_result.confidence == 0.92


def test_start_stop_does_not_crash() -> None:
    """Start and stop the ingest task without error."""
    ingest = RecordingAiIngest(
        output_path=Path("/tmp/rec.mp4"),
        get_session_id=lambda: 1,
        persistence=MagicMock(),
        interval_sec=0.05,
        startup_delay_sec=0.01,
    )
    ingest.start()
    time.sleep(0.08)
    ingest.stop()
