# Detection Usability Implementation Plan

## Order of Work

1. **Save last detection result** (Option 1)
2. **Add confidence threshold** (Option 2)
3. **Add event normalization** (Option 3)

Each step builds on the previous without churn.

---

## Option 1: Save Last Detection Result (Phase 1)

### API Design

- **POST /api/ai/detect** — Run detection, update cache on success
- **GET /api/ai/last-detection** — Return cached result (dedicated endpoint)

Do **not** put last detection inside `/api/ai/status`. Status stays about readiness/capability; last detection is runtime result data.

### Store Shape

Store:

- Full `DetectionResult`
- Timestamp
- Optional: short summary string, `source="camera"`

### Cache Overwrite Policy

**Phase 1 (small):** Store only `last_successful_detection`.

Overwrite cache only when:

- `state === "ready"` (detections found)
- `state === "no_detections"` (clean run, nothing found)

Do **not** overwrite a good cached result with a transient error. That keeps UX stable.

If you later want "last attempt" semantics, add `last_detection_attempt` separately.

### Implementation

- New: `AiDetectionStore` (thread-safe)
- POST /api/ai/detect: on success (`ready` or `no_detections`), store result + timestamp
- GET /api/ai/last-detection: return cached result or 404/empty
- Dashboard: fetch last result on refresh, show "Last: person, car (2) at 2:34 PM"

---

## Option 2: Confidence Threshold

Add a dedicated config:

- **AI_HAT_DETECTION_THRESHOLD** (0.0–1.0)

Do **not** reuse `AI_MIN_CONFIDENCE` from mission logic. Keep Hailo and mission logic thresholds separate for clear semantics.

Filter detections in `hailo_detection_impl` before building `DetectionResult`.

---

## Option 3: Event Normalization

Do this **third**, after:

- Detection quality is trusted
- Label mapping is stable
- Threshold behavior is understood

Then add compact events: `person_detected`, `vehicle_detected`, `object_count`.

---

## Summary

- Dedicated GET /api/ai/last-detection
- Cache last successful result only (ready or no_detections)
- Separate AI_HAT_DETECTION_THRESHOLD for Option 2
- Event normalization last, once detection pipeline is solid
