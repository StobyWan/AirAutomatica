# AI HAT Subsystem Scope

## Subsystem Definition

The **AI HAT subsystem** is an optional perception/copilot-support module for the Raspberry Pi companion computer. It provides edge vision acceleration via the Raspberry Pi AI HAT+ (Hailo-8L) and delivers structured object detections and normalized events. It is additive to the main AirAutomatica stack—telemetry, mission logic, and persistence—and does not replace or override them.

## Current Capability

- **Hardware detection:** Detects presence of Hailo-8L via PCIe; reports device class, board name, driver readiness.
- **Status and diagnostics:** `GET /api/ai/status` (capability/config) and `GET /api/ai/diagnostics` (troubleshooting).
- **One-shot structured detection:** `POST /api/ai/detect` captures one frame, runs YOLOv6 inference, returns labels, confidence, bounding boxes.
- **Last one-shot cache:** `GET /api/ai/last-detection` returns the most recent successful one-shot result. UI shows "AI HAT last one-shot" with stale age.
- **Detection threshold:** Configurable `AI_HAT_DETECTION_THRESHOLD` (0–1) suppresses weak detections.
- **Event normalization:** Raw detections mapped to canonical events (`person_detected`, `vehicle_detected`, `object_count`).
- **person_detected hook:** When one-shot detects a person, a system event is appended (when persistence and session available).

## Not Yet / Out of Scope

- **Continuous or streaming detection:** No repeated inference loop; only on-demand one-shot.
- **Flight control integration:** AI HAT does not send commands to the flight controller.
- **Recording integration:** AI HAT one-shot is independent of camera recording.
- **Session-linked AI HAT history:** One-shot results are cached in memory; persisted detection history comes from mission flow (Ollama/mock), not from AI HAT one-shot.
- **AI HAT+ 2 / Hailo-10:** Hardware target is Hailo-8L only.

## Relation to Companion Computer

The AI HAT runs on the Raspberry Pi 5 companion computer. It is a companion-side perception layer: it reads camera frames, runs inference, and produces structured detections. The companion app aggregates telemetry, AI results, and system events; the AI HAT contributes to that aggregation without controlling flight.

## Relation to Flight Controller

The AI HAT is **not** flight-critical. It does not read MAVLink directly; it does not send commands. The flight controller remains the source of truth for aircraft state. AI HAT detections are advisory and logged; they do not control the autopilot.

## AI HAT Detections vs Persisted Mission Detections

| Concept | Source | Storage | UI |
|--------|--------|---------|-----|
| **AI HAT last one-shot** | `POST /api/ai/detect` | In-memory cache | "AI HAT last one-shot: person, car (2) — 18s ago" |
| **Persisted detection history** | Mission flow (Ollama/mock) via `insert_detection` | SQLite `detections` | "Recent Detections" / "Persisted mission-flow detection history" |

AI HAT one-shot results are cached for display and quick reference. Persisted detections come from the mission logic loop (Ollama or mock) and are stored in the database. They are distinct data flows.

---

## Glossary

| Term | Definition |
|------|------------|
| **AI HAT** | Raspberry Pi AI HAT+ add-on board for edge vision. |
| **AI HAT+** | Same as AI HAT; the "+" denotes the Hailo variant. |
| **Hailo-8L** | Hailo-8L AI processor on the AI HAT+. Target hardware. |
| **AI HAT capability** | Whether hardware is present and runtime is ready. |
| **One-shot detection** | Single capture + inference on demand. Not continuous. |
| **Last one-shot result** | Cached result of the most recent successful one-shot run. |
| **Persisted detection history** | Detections stored in SQLite from mission flow (Ollama/mock). |
| **Structured detections** | Raw output: label, confidence, bbox per object. |
| **Normalized events** | Canonical events: `person_detected`, `vehicle_detected`, `object_count`. |
| **Threshold** | `AI_HAT_DETECTION_THRESHOLD`; minimum confidence to include a detection. |
| **Diagnostics** | Deep troubleshooting output (lspci, hailortcli, paths, config). |
| **Perception** | Vision-based inference; not flight control. |

---

## Roadmap

### Phase A: Capability and Readiness — Implemented

- Hardware detection (PCIe, Hailo device)
- Status endpoint (`GET /api/ai/status`)
- Diagnostics endpoint (`GET /api/ai/diagnostics`)
- Graceful degradation when hardware absent

### Phase B: One-Shot Structured Detection — Implemented

- One-shot capture (`rpicam-still`) + inference (Hailo/YOLOv6)
- Structured detections (label, confidence, bbox)
- Detection threshold config
- Last-result cache (`GET /api/ai/last-detection`)

### Phase C: Detection Usability — Implemented

- Normalized events
- Clear UI labels (AI HAT last one-shot vs persisted history)
- Stale-age display
- Threshold display in UI
- person_detected → system event hook

### Phase D: Future Expansion — Not Implemented

- Event-driven repeated detection
- Recording integration
- Perception-triggered workflows
- Session-linked AI HAT result history
