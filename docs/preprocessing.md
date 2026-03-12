# Telemetry Preprocessing Pipeline

## Overview

The preprocessing pipeline reduces raw ArduPilot/INAV telemetry into compact, high-value summaries before sending anything to the local Llama model. Python handles deterministic math, time-series analysis, trend detection, and event detection; Llama is used only for small advisory tasks on preprocessed summaries.

## Phase 2 Implementation (Current)

### Files Added

| Path | Purpose |
|------|---------|
| `flight_phase_engine.py` | FlightPhaseEngine with mode-first classification and hysteresis |
| (plus Phase 1 files) | feature_engine, event_engine, context_builder, pipeline, etc. |

### Files Modified

| Path | Change |
|------|--------|
| `feature_engine.py` | Added groundspeed_mean_medium for mission_progress_stall |
| `event_engine.py` | Added heading_drift, mission_progress_stall |
| `context_builder.py` | Improved trend summary: phase + events + metrics |
| `pipeline.py` | Wired FlightPhaseEngine; replaced stub phase |

## Flight Phase Design

**Priority order:** disarmed → mode-based (RTL, LOITER, landing, takeoff) → motion-based (climb, cruise, descent) → unknown.

**Mode-based (authoritative):** When mode is clearly trustworthy:
- RTL → rtl
- LOITER / CIRCLE → loiter
- QLAND / AUTOLAND → landing
- TAKEOFF → takeoff

**Motion-based (generic modes):** For AUTO, GUIDED, FBWA, FBWB, CRUISE, STABILIZE:
- climb_rate > 0.5 → climb
- climb_rate < -0.5 → descent
- groundspeed > 2 → cruise
- else → unknown

**Hysteresis:** hold_samples (default 3) consecutive samples required before phase transition to avoid flapping.

## Features Implemented

| Feature | Source | Notes |
|---------|--------|------|
| roll_var, pitch_var | short buffer | Attitude variance |
| heading_change_rate_deg_s | short buffer | Delta / dt |
| altitude_rate_m_s | current climb_rate | Climb/descent |
| voltage_trend, current_trend | medium buffer | Linear slope |
| watts | current | voltage_v * current_a |
| distance_to_home_m | lat, lon, home | Haversine |
| home_bearing_deg, relative_bearing_deg | lat, lon, home, heading | Navigation |
| estimated_endurance_s | voltage, current, threshold | Conservative: (v - min) * 3600 / i |
| endurance_confidence | low, medium, high | medium when stable for N samples |
| return_margin_s | endurance - time_to_home | Only when confidence >= medium |
| groundspeed_mean_medium | medium buffer | For mission_progress_stall |

## Events Implemented

| Event | Condition | Hysteresis |
|-------|-----------|------------|
| gps_degraded | satellites < 6 or fix_type < 3 | 3 open, 3 clear |
| battery_sag | voltage < 11V or voltage_trend < -0.15 | 3 open, 3 clear |
| high_power_draw | watts > 150W | 3 open, 3 clear |
| unstable_attitude | roll_var or pitch_var > 0.05 | 3 open, 3 clear |
| altitude_loss | altitude_rate < -3 m/s | 3 open, 3 clear |
| weak_return_margin | return_margin_s < 60 | 3 open, 3 clear |
| heading_drift | abs(heading_change_rate) > 15 deg/s | 3 open, 3 clear |
| mission_progress_stall | mode AUTO/GUIDED, groundspeed_mean < 0.5 m/s | 3 open, 3 clear |

## Trend-Summary Behavior

One operator-focused sentence: **[phase] with [top events], [power label], [distance from home].**

Examples:
- "Cruise flight with moderate power draw, 540 m from home."
- "Descent flight with weak return margin."
- "RTL active with gps degraded. 2.1 km from home."
- "Unknown with low power draw."

Event priority for inclusion: gps_degraded, battery_sag, weak_return_margin, unstable_attitude, altitude_loss, high_power_draw, heading_drift, mission_progress_stall.

## LLM Payload Contract

- **top_events:** 3 (pad with empty if fewer)
- **top_metrics:** 5 keys in fixed order: voltage_v, rel_alt_m, groundspeed_m_s, distance_to_home_m, estimated_endurance_s
- **trend_summary:** 1 sentence (phase + events + metrics)
- **estimated_endurance_s:** -1 when confidence < medium (sentinel for unavailable)

## Known Limitations

- Endurance model is naive (voltage margin / current); no battery capacity
- Mission modes: only AUTO and GUIDED checked for mission_progress_stall
- Thresholds are tuned for typical fixed-wing; may need adjustment for other platforms
- Phase hysteresis is sample-based, not time-based

## Ollama Input Policy

Ollama receives only compact, preprocessed context—never raw telemetry:

- **Telemetry summary:** `LlmContextPayload` (phase, mode, trend_summary, top 3 events, top 5 metrics). When preprocessing is disabled and provider=ollama, the API returns an error; preprocessing is required.
- **Debrief summary:** `CompactDebriefPayload` (duration, dominant phase, top events, top metrics, assessment).
- **Event classification:** Up to 5 events as `event_type: message[:60]`.

Raw `TelemetrySample` rows, full `AircraftState`, or unbounded arrays are never sent to Ollama.

## API Changes

- No breaking changes. Fallback behavior preserved when preprocessor is None and provider=mock. When provider=ollama, preprocessing is required for telemetry summary.

---

## Debrief Engine

Post-flight/session summary from recorded telemetry. Deterministic, lightweight, reuses FeatureEngine, EventEngine, and FlightPhaseEngine.

### Purpose

Produce a useful post-flight summary from recorded telemetry/session data for operator review or local Llama summarization.

### Inputs

- **Source:** `TelemetrySample` rows via `PersistenceService.get_session_telemetry_for_debrief(session_id)`
- **Data:** Stored telemetry samples (oldest first), including lat, lon, voltage_v, current_a, mode, attitude, etc.
- **Home:** First sample's lat/lon used as home for distance-to-home and return-margin calculations

### Outputs

**DebriefSummary** (structured):

- `session_duration_sec` – Total flight/session duration
- `phase_duration_sec` – Per-phase duration breakdown (cruise, rtl, climb, etc.)
- `peak_distance_from_home_m` – Max distance from home
- `average_power_w`, `peak_power_w` – Power aggregates
- `minimum_voltage_v` – Lowest voltage
- `top_events` – Event stats (name, count, duration_sec), sorted by duration desc
- `weak_return_margin_occurred`, `gps_degraded_occurred`, `unstable_attitude_occurred` – Boolean flags
- `assessment_tags` – Deterministic tags: stable, power_hungry, return_risk, gps_limited, attitude_unstable, battery_concern

**CompactDebriefPayload** (for local Llama):

- `total_duration_sec` – Session duration
- `dominant_phase` – Phase with longest duration
- `top_3_event_summaries` – Exactly 3 event summaries (name + duration)
- `top_5_metrics` – Exactly 5 key-value pairs (duration_sec, peak_distance_m, avg_power_w, peak_power_w, min_voltage_v)
- `assessment_sentence` – One concise trend/assessment sentence

### Compact Debrief Payload Contract

- Fixed shape: 3 event summaries, 5 metrics, 1 sentence
- Deterministic ordering: events by duration desc, metrics in fixed order
- Small payload suitable for local Llama on Raspberry Pi 5

### Known Limitations

- **gps_degraded:** Never triggered from recorded samples (satellites_visible, gps_fix_type not stored in TelemetrySample)
- **Home:** Uses first sample as home; no explicit home position from mission
- **Climb rate:** Derived from consecutive rel_alt_m deltas
- Replay is O(n) over samples; typical flights (~1000 samples) are fine

### Integration

- **API:** `GET /sessions/{sid}/debrief` – Returns summary + compact payload, 404 if no telemetry
- **API (LLM):** `GET /sessions/{sid}/debrief?generate_summary=true` – Adds `generated_summary` when task_service available
- **Service:** `get_session_debrief(session_id, persistence)` – Helper callable, returns (summary, compact) or (None, None)
- **Service (LLM):** `get_session_debrief_with_llm(session_id, persistence, task_service)` – Returns (summary, compact, generated_summary)

---

## Debrief LLM Flow

Post-flight summary generation via local Llama. Uses compact debrief payload only; no raw telemetry.

### Flow

1. **Structured debrief** – DebriefEngine generates DebriefSummary from TelemetrySample rows
2. **Compact payload** – `build_compact_debrief_context(summary)` produces CompactDebriefPayload
3. **Prompt** – `compact_debrief.to_dict()` passed as `compact_debrief` context to DEBRIEF_SUMMARY task
4. **Llama** – Task service invokes Ollama with schema-based JSON output
5. **Result** – DebriefSummaryResult with 2–4 sentence summary

### Compact Payload to Prompt Contract

- **Input:** `context["compact_debrief"]` = `CompactDebriefPayload.to_dict()`
- **Fields used:** total_duration_sec, dominant_phase, top_3_event_summaries, top_5_metrics, assessment_sentence
- **No raw telemetry:** Prompt never receives TelemetrySample rows or large arrays
- **Output schema:** `{"summary": "string"}` – 2–4 sentences max

### Prompt Design

- Summarize session briefly
- Highlight most important issue or condition
- Mention one practical thing to monitor or improve next time
- Grounded in evidence; no exaggerated certainty; no fabricated causes

### Fallback Behavior

- **task_service is None:** `generate_summary=true` has no effect; response omits `generated_summary`
- **Ollama disabled (provider=mock):** Returns mock summary
- **Ollama fails:** Returns fallback `DebriefSummaryResult(summary="Debrief summary unavailable: ...")`
- **Parse error:** Parser returns empty summary; API includes `generated_summary: null` or fallback text

### Known Limitations

- Small models (e.g. gemma3:1b) may produce generic or truncated summaries
- No retry or timeout tuning specific to debrief
- Generated summary not persisted; must be requested per call

### Dashboard Debrief Display

The session detail page (`/dashboard/sessions/{id}`) shows a debrief card when telemetry exists.

**Behavior:**
- **Page load:** Fetches `GET /sessions/{sid}/debrief` without `generate_summary`. No LLM call on page load.
- **Structured metrics:** Renders session duration, dominant phase, peak distance from home, average/peak power, minimum voltage, top events (max 5), and assessment tags as compact badges.
- **AI summary:** Only requested when the operator clicks "Generate AI Summary". Fetches `GET /sessions/{sid}/debrief?generate_summary=true`. Prevents duplicate concurrent requests.
- **Isolation:** Debrief fetch failure does not affect the rest of the session page. Errors are confined to the debrief section.

**Fallback behavior:**
- **404:** "No debrief data for this session."
- **Other fetch failure:** "Debrief could not be loaded."
- **No generated summary:** Placeholder "AI summary not generated yet." with Generate button.
- **AI generation failure:** "AI summary could not be generated." (calm message, no raw error text).

### Generated Summary Persistence

Generated debrief summaries are persisted in `flight_sessions` (`generated_debrief_summary`, `generated_debrief_at`).

**Behavior:**
- **On generation:** When `GET /sessions/{sid}/debrief?generate_summary=true` succeeds, the generated summary is saved. Fallback/error text (e.g. "Debrief summary unavailable: ...") is not persisted.
- **On page load:** When `GET /sessions/{sid}/debrief` is called without `generate_summary`, the API includes `generated_summary` and `generated_debrief_at` (ISO timestamp) from persistence if one exists. No LLM call.
- **Regenerate:** The session detail page shows a "Regenerate AI Summary" button when a summary exists. Clicking it calls `generate_summary=true` again and overwrites the persisted summary on success.

**Regenerate semantics:**
- Regenerate overwrites the stored summary; no version history.
- On failure: if a summary already existed, it remains displayed; a subtle "Regeneration failed." message is shown. If no summary existed, the placeholder shows "AI summary could not be generated."

**Timestamp display:**
- When `generated_debrief_at` is present in the API response, the summary card shows "Generated on …" (locale-formatted).

**Fallback when persistence unavailable:**
- If `get_engine()` is None, `get_generated_debrief` returns None; response omits `generated_summary`.
- Structured debrief still works; only the persisted summary is absent.

### Recommended Next Step After Llama Debrief Integration

1. **Prompt tuning** – Adjust for target model size and operator feedback
