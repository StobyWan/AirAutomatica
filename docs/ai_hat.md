# AI HAT Support (Raspberry Pi AI HAT+ / Hailo-8L)

AirAutomatica supports **optional** Raspberry Pi AI HAT+ (Hailo-8L / Hailo-8) for onboard vision acceleration. This is a capability, not a requirement—the app runs fully without AI HAT hardware.

**AI HAT+ 2 / Hailo-10 is NOT the current target.** This document covers the original AI HAT+ with Hailo-8L only.

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

Use the helper script (run manually on Pi with AI HAT):

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

Expected output includes:

- **Board Name:** Hailo-8
- **Device Architecture:** HAILO8L

### 4. Test camera + Hailo postprocess

```bash
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov6_inference.json
```

## Enabling AI HAT

1. Install Hailo packages (see above)
2. Set `AI_HAT_ENABLED=1` in `/etc/airautomatica/airautomatica.env` or in Settings
3. Restart the service

## API and Diagnostics

- **GET /api/ai/status** — AI HAT capability status (enabled, detected, state, device_class, etc.)
- **GET /api/ai/diagnostics** — Detailed troubleshooting output (includes `object_detection` block)
- **POST /api/ai/detect** — One-shot object detection (see below)
- **CLI:** `airautomatica --diagnose-ai` — Print diagnostics and exit

## Object Detection (One-Shot)

Real structured object detection returns labels, confidence, and bounding boxes (normalized 0..1).

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

### Endpoint

**POST /api/ai/detect** — No body. Returns:

```json
{
  "backend": "hailo",
  "model": "yolov6n",
  "state": "ready" | "no_detections" | "error" | "disabled" | "unavailable",
  "structured_output_supported": true,
  "detections": [
    {
      "label": "person",
      "confidence": 0.91,
      "bbox": {"x": 0.12, "y": 0.18, "width": 0.34, "height": 0.52},
      "source": "camera"
    }
  ],
  "frame_width": 640,
  "frame_height": 480,
  "inference_time_ms": 23.4,
  "errors": []
}
```

Bbox coordinates are normalized 0..1 (x, y = top-left; width, height = size).

### Config Flags

- `AI_HAT_ENABLED` — Must be 1 for detection
- `AI_HAT_OBJECT_DETECTION_ENABLED` — Must be 1 (default when AI HAT enabled)
- `AI_HAT_CAMERA_PIPELINE_ENABLED` — Must be 1 (default when AI HAT enabled)

### UI Test

Connection & Health → AI HAT → **Run AI Detection Test**. Shows state, count, labels, confidences, bboxes, errors.

### Limitations (Phase 1)

- One-shot only; no continuous streaming
- Single model: yolov6n_h8l.hef
- Camera contention: if recording is active, capture may fail with "camera busy"
- hailo-apps is optional; install for real structured detections

### Future

- Continuous or event-driven detection
- Additional model support

## Dashboard

The Connection & Health card shows an **AI HAT (optional)** section with:

- Backend (Hailo / None)
- Hardware detected (yes / no)
- Device (e.g. Hailo-8L)
- State (ready / missing_cli / missing_hardware / identify_failed / disabled / misconfigured)
- **Run AI Detection Test** button for one-shot detection
