# Detection Configuration

Single reference for all AI HAT detection-related settings. Resolved by `get_detection_config()` in `config.py`.

## Config Matrix

| Field | Env var | Default | Description |
|-------|---------|---------|-------------|
| `ai_hat_enabled` | AI_HAT_ENABLED, AI_MODE | false (unless AI_MODE=aihat) | Master switch for AI HAT layer |
| `ai_hat_camera_pipeline_enabled` | AI_HAT_CAMERA_PIPELINE_ENABLED | 1 when AI HAT enabled | Camera pipeline for one-shot capture |
| `ai_hat_object_detection_enabled` | AI_HAT_OBJECT_DETECTION_ENABLED | 1 when AI HAT enabled | Object detection capability |
| `inference_threshold` | AI_HAT_DETECTION_THRESHOLD | 0.25 | Min confidence at inference time; filters raw model output |
| `recording_overlay_enabled` | RECORDING_AI_OVERLAY_ENABLED | 1 when AI HAT enabled | Bounding-box overlay on recorded video |
| `recording_persist_enabled` | RECORDING_AI_PERSIST_ENABLED | 1 when AI HAT enabled | Persist recording-time detections to DB |
| `recording_persist_interval_sec` | RECORDING_AI_PERSIST_INTERVAL_SEC | 5 | Seconds between frame extractions |
| `recording_persist_startup_delay_sec` | RECORDING_AI_PERSIST_STARTUP_DELAY_SEC | 3 | Grace period before first extraction |
| `persist_threshold` | RECORDING_AI_PERSIST_THRESHOLD | 0.5 | Min confidence to persist; must be >= inference_threshold for detections to reach DB |

## Dependency Chain

```
ai_hat_enabled
  ├── ai_hat_camera_pipeline_enabled
  ├── ai_hat_object_detection_enabled
  ├── recording_overlay_enabled
  └── recording_persist_enabled
```

Overlay and persist are independent of each other. Both default to enabled when AI HAT is enabled. **Mutual exclusion at runtime:** overlay and persist both use the Hailo device; only one can run. When overlay is enabled, RecordingAiIngest is not created (device in use). Use overlay=0 for persist detections.

## Threshold Semantics

Two thresholds exist by design:

- **inference_threshold** (AI_HAT_DETECTION_THRESHOLD, default 0.25): Applied when building `DetectionResult` from raw model output. Detections below this are dropped before the result is returned. Keeps one-shot and recording-time responses free of weak detections.

- **persist_threshold** (RECORDING_AI_PERSIST_THRESHOLD, default 0.5): Applied when persisting recording-time detections to the database. Stricter than inference so that Recent Detections shows only higher-confidence items. Aligns with AI_MIN_CONFIDENCE (mission logic).

For a recording-time detection to appear in Recent Detections: `confidence >= inference_threshold` (to pass inference) and `confidence >= persist_threshold` (to be persisted).

## Recording-Time Persist: Session Required

RecordingAiIngest is only created when a session is active. If you start recording without starting a session first, the ingest thread is not created and no detections are persisted. Start session before recording for detections.

## Usage

```python
from airautomatica.config import get_detection_config

cfg = get_detection_config()
if cfg.recording_persist_enabled:
    interval = cfg.recording_persist_interval_sec
    threshold = cfg.persist_threshold
```

Individual getters (`get_ai_hat_enabled()`, etc.) delegate to `get_detection_config()` and remain available for backward compatibility.
