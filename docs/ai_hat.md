# AI HAT Subsystem

Optional perception subsystem for the Raspberry Pi companion computer. Uses the Raspberry Pi AI HAT+ (Hailo-8L) for edge vision acceleration. See [ai_hat_scope.md](ai_hat_scope.md) for subsystem definition, glossary, and roadmap.

## What the AI HAT Subsystem Is

- **Optional** edge perception hardware
- **One-shot** visual detection today (on-demand capture + inference)
- **Companion-side** only—not flight-critical, does not control the autopilot
- **Foundation** for future perception-assisted aviation workflows

## What It Is Not

- Not flight-critical
- Not autopilot logic
- Not a general AI abstraction for the whole app
- Not continuous autonomous perception (yet)
- Not a replacement for MAVLink or flight controller state

## Graceful Degradation

When AI HAT hardware is absent or packages are missing:

- The app starts and runs normally
- AI HAT status is reported as `disabled`, `missing_cli`, `missing_hardware`, or `identify_failed`
- No startup failure; no hard dependency on Hailo packages

## Required Packages

On Raspberry Pi with AI HAT hardware, install:

- `hailo-all`
- `hailo-models`
- `hailo-tappas-core`
- `hailort`
- `hailort-pcie-driver`
- `python3-hailort`
- `python3-hailo-tappas`
- `rpicam-apps-hailo-postprocess`

Helper script (run manually on Pi with AI HAT):

```bash
sudo packaging/linux/install-ai-hat-deps.sh
```

## Verification

### 1. Check installed packages

```bash
dpkg -l | grep hailo
```

### 2. Check PCIe device

```bash
lspci
```

Expected: `Hailo Technologies Ltd. Hailo-8 AI Processor`

### 3. Identify Hailo device

```bash
hailortcli fw-control identify
```

Expected: Board Name Hailo-8, Device Architecture HAILO8L

### 4. Test camera + Hailo postprocess

```bash
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov6_inference.json
```

## Enabling AI HAT

1. Install Hailo packages (see above)
2. Set `AI_HAT_ENABLED=1` in `/etc/airautomatica/airautomatica.env` or in Settings
3. Restart the service

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/ai/status` | Capability and current config/readiness. Returns enabled, detected, state, device_class, detection_threshold, etc. |
| `GET /api/ai/diagnostics` | Deep troubleshooting: lspci, hailortcli, paths, object_detection block. |
| `POST /api/ai/detect` | Execute a new one-shot detection. Returns structured detections and normalized events. |
| `GET /api/ai/last-detection` | Cached result of the most recent successful one-shot detection. |

**CLI:** `airautomatica --diagnose-ai` — Print diagnostics and exit.

## One-Shot Object Detection

Structured object detection returns labels, confidence, and bounding boxes (normalized 0..1).

### Requirements

- Hailo packages (install-ai-hat-deps.sh)
- **hailo-apps** (optional): `pip install hailo-apps` or `git clone hailo-apps && ./install.sh`
- **rpicam-still** for frame capture
- HEF model: `/usr/share/hailo-models/yolov6n_h8l.hef` (from hailo-models package)

Without hailo-apps, detection returns `state="unavailable"` with a clear error.

Optional install script:

```bash
packaging/linux/install-ai-hat-apps.sh
```

### POST /api/ai/detect Response

```json
{
  "backend": "hailo",
  "model": "yolov6n",
  "state": "ready",
  "structured_output_supported": true,
  "detections": [
    {
      "label": "person",
      "confidence": 0.91,
      "bbox": {"x": 0.12, "y": 0.18, "width": 0.34, "height": 0.52},
      "source": "camera"
    }
  ],
  "events": [
    {"event_type": "person_detected", "label": "person", "confidence": 0.91, "count": 1},
    {"event_type": "object_count", "count": 1, "metadata": {"labels": ["person"]}}
  ],
  "frame_width": 640,
  "frame_height": 480,
  "inference_time_ms": 23.4,
  "errors": []
}
```

Bbox coordinates are normalized 0..1 (x, y = top-left; width, height = size).

### Config Flags

| Variable | Purpose |
|----------|---------|
| `AI_HAT_ENABLED` | Must be 1 for detection |
| `AI_HAT_OBJECT_DETECTION_ENABLED` | Must be 1 (default when AI HAT enabled) |
| `AI_HAT_CAMERA_PIPELINE_ENABLED` | Must be 1 (default when AI HAT enabled) |
| `AI_HAT_DETECTION_THRESHOLD` | Min confidence 0–1; default 0.25. Suppresses weak detections. |

## Cached vs Persisted

| Concept | Storage | Lifecycle |
|---------|---------|-----------|
| **Last one-shot result** | In-memory cache | Overwritten on each successful one-shot run. Lost on restart. |
| **Persisted detection history** | SQLite `detections` | From mission flow (Ollama/mock). Survives restart. |

AI HAT one-shot results are cached for quick display. Persisted detections come from the mission logic loop and are stored in the database. They are distinct.

## Dashboard UI

The Connection & Health card shows an **AI HAT (optional)** section:

- **Backend** — Hailo or None
- **Hardware detected** — yes / no
- **Device** — e.g. Hailo-8L
- **State** — ready / missing_cli / missing_hardware / identify_failed / disabled / misconfigured
- **Threshold** — Active detection threshold (e.g. 0.25)
- **Run one-shot detection** — Triggers one-shot detection
- **AI HAT last one-shot** — Cached result with stale age (e.g. "person, car (2) — 18s ago")

**Recent Detections** (separate card) shows persisted mission-flow detection history, not AI HAT one-shot results.

## Current Limitations

- One-shot only; no continuous streaming
- Single model: yolov6n_h8l.hef
- Camera contention: if recording is active, capture may fail with "camera busy"
- hailo-apps is optional; install for real structured detections
- AI HAT+ 2 / Hailo-10 is not supported

## Near-Term Next Steps

See [ai_hat_scope.md](ai_hat_scope.md) Phase D for future expansion ideas: event-driven repeated detection, recording integration, perception-triggered workflows, session-linked AI HAT result history.
