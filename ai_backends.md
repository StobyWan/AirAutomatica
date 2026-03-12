# AI Service

AIRAUTOMATICA uses a single AI service abstraction with mode-based implementations. Mission logic consumes only normalized `AiResult`—it does not depend on which mode produced it.

## Architecture: Mission Loop + Advisory LLM + Optional AI HAT

- **Mission loop perception**: Uses mock or AI HAT only. Ollama is not used for live perception.
- **Ollama (advisory)**: Used only for dashboard tasks—telemetry summary, debrief summary, event classification. Consumes compact preprocessed context only.
- **AI HAT**: Optional hardware-accelerated vision layer; runs **alongside** mock when enabled. ComposedAiService tries AI HAT first; if meaningful, uses it; else uses mock.

## Modes

| Mode | Purpose | Environment |
|------|---------|-------------|
| **mock** | Deterministic fake results for tests and early development. No network or hardware. | macOS, Raspberry Pi |
| **ollama** | Local inference via [Ollama](https://ollama.com/) HTTP API (POST /api/generate). Provides reasoning/advisory on preprocessed summaries (telemetry summary, debrief, event classification). AI HAT provides vision/perception. They are complementary, not substitutes. | macOS, Linux |
| **aihat** | Raspberry Pi AI HAT+ onboard perception. Vision/detection only—runs **with** mock or ollama, not instead. | Raspberry Pi 5 |

## Configuration

```bash
# AI provider: ollama (default) or mock
export LOCAL_LLM_PROVIDER=ollama
export LOCAL_LLM_BASE_URL=http://127.0.0.1:11434
export LOCAL_LLM_MODEL=gemma3:1b
export LOCAL_LLM_TIMEOUT=30

# AI HAT: enable alongside local provider
export AI_HAT_ENABLED=0

# Mission logic filtering: min confidence to persist; duplicate window (sec)
export AI_MIN_CONFIDENCE=0.5
export AI_DUPLICATE_WINDOW_SEC=30

# AI HAT (when AI_HAT_ENABLED=1)
export AIHAT_MODEL_NAME=default
# AIHAT_DEVICE: placeholder. Real AI HAT+ uses HailoRT device discovery; no path needed.
export AIHAT_DEVICE=auto
```

## Local Development (macOS / Linux)

1. **Ollama mode** (default): Install [Ollama](https://ollama.com/), pull a model (`ollama pull gemma3:1b`), start the server (runs automatically). Ollama provides reasoning/advisory on preprocessed summaries (telemetry summary, debrief, event classification).
   ```bash
   make setup-ollama
   python -m airautomatica.main
   ```

2. **Mock mode**: No setup. AI results are deterministic fakes.
   ```bash
   LOCAL_LLM_PROVIDER=mock python -m airautomatica.main
   ```
   Mission loop perception uses mock or AI HAT. Ollama is used only for dashboard advisory tasks (telemetry summary, debrief, event classification).

## What AI HAT Mode Really Means

AI HAT mode = **onboard vision perception** on Raspberry Pi 5 + AI HAT+.

- **Hardware**: Hailo-8/8L NPU on PCIe. Object detection, segmentation, pose.
- **Not**: An LLM, a drop-in for Ollama, or general "AI reasoning."
- **Input**: Camera frames (rpicam). **Output**: Detections (label, confidence, bbox).
- **In this project**: Mission logic gets AiResult; applies rules. Non-flight-critical.
- **Ollama**: Used for advisory tasks (telemetry summary, debrief, event classification). Consumes only compact preprocessed context—never raw telemetry.

## AI HAT Mode: Onboard Perception

In flight, AI HAT mode provides **onboard perception** (vision, object detection), not LLM reasoning. The mission logic interprets `AiResult` and applies action rules. Phase 1 does not run an LLM onboard.

To switch from Ollama (dev) to AI HAT (Raspberry Pi 5):

1. Set `AI_HAT_ENABLED=1` and configure `AIHAT_MODEL_NAME`, `AIHAT_DEVICE`.
2. Complete the `AiHatAiService` implementation using Hailo SDK or Pi AI Kit.
3. No refactoring of mission logic—only service implementation and config.

## AI Result Contract

All modes produce the same normalized `AiResult`. Mission logic is backend-agnostic and consumes only this contract.

| Field | Type | Required | Description | Normalization |
|-------|------|----------|-------------|---------------|
| `label` | str | yes | Detection/inference label | Non-empty; default `"unknown"` |
| `confidence` | float | yes | 0.0–1.0 | Clamped to [0, 1] |
| `summary` | str | yes | Human-readable summary | Default `""` |
| `source_backend` | str | yes | `mock`, `ollama`, or `aihat` | Set by service |
| `timestamp` | datetime | yes | When produced | UTC |
| `bbox` | tuple \| None | no | (x, y, w, h) for detections | 4 floats or None |
| `action` | str \| None | no | Optional suggested action | None if empty |
| `metadata` | dict \| None | no | Allowed keys only; see below | — |

### Metadata Guidelines

`metadata` is for debugging and backend-specific extras—not a junk drawer. Only these keys are allowed:

| Key | Backend | When |
|-----|---------|------|
| `error` | ollama | True when inference failed |
| `parse_error` | ollama | `"json"` or `"content"` when parsing failed |
| `error_type` | ollama | `"timeout"`, `"http"`, or `"network"` |
| `raw_length` | ollama | Length of raw LLM response |
| `call_count` | mock | Incrementing call index |
| `mode` | mock | Aircraft mode from state |
| `model_name` | aihat | Model name from config |
| `device` | aihat | Device config from env (placeholder; HailoRT auto-discovers) |
| `todo` | aihat | Scaffold placeholder |

## TODO: AI HAT Implementation

The `AiHatAiService` scaffold exists but returns a placeholder. To complete:

- Integrate with Raspberry Pi AI HAT+ via `hailo-all` / HailoRT Python API
- Add camera input (rpicam, picamera2); real inference needs frames, not just state
- Load HEF model from Hailo Model Zoo (see `AIHAT_MODEL_NAME`)
- HailoRT auto-discovers PCIe device; no device path needed
- Map raw detection output to normalized `AiResult` (label, confidence, bbox, etc.)
- See hailo-rpi5-examples on GitHub for reference
