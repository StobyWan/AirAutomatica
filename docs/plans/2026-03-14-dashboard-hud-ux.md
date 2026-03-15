# Dashboard Recording/Session HUD UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the Operations card into a professional operator HUD with instant feedback during session/recording stop transitions, and a polished status-at-a-glance layout.

**Architecture:** Local transient state (with timestamps) overrides backend truth from health_update until reconciled. Derived button rendering from single render function. Transition row as first-class operator feedback channel.

**Tech Stack:** Plain HTML/JS, Tailwind CSS, Socket.IO (no framework changes).

---

## 1. Root Problem Summary

| Problem | Cause |
|---------|-------|
| UI feels stuck when stopping session/recording | `POST /session/stop` and `POST /camera/recording/stop` block until backend finishes. `stop_recording()` waits up to 8s for rpicam-vid to finalize MP4 moov atom. The fetch does not resolve until then. |
| No in-progress feedback | Buttons disable on click but show no "Stopping…" label, spinner, or helper text. |
| health_update overwrites UI | Socket emits every 1s. No transient state to show "Stopping…" while backend catches up. |

---

## 2. Transient State (with Timestamps)

```javascript
const transientState = {
  stoppingSession: false,
  stoppingSessionSince: null,      // Date.now() when user clicked
  stoppingRecording: false,
  stoppingRecordingSince: null,
  startingSession: false,
  startingSessionSince: null,
  startingRecording: false,
  startingRecordingSince: null,
};
```

**Why timestamps:** Handles out-of-order health updates, enables timeout logic, and aids debugging. When reconciling, compare `stoppingSessionSince` to know which optimistic state is current.

---

## 3. Derived Button Rendering

**Avoid manual text mutation.** Drive all labels from a single render function that takes backend state + transient state:

| Button | Idle label | Transient label |
|--------|------------|-----------------|
| Stop Session | Stop Session | Stopping… |
| Stop Recording | Stop Recording | Stopping… |
| Start Session | Start Session | Starting… |
| Start Recording | Start Recording | Starting… |

**Implementation:** One `renderOperationsButtons()` (or similar) that:
1. Reads `transientState` and backend-derived state
2. Sets `button.textContent`, `button.disabled`, spinner visibility
3. Called on: click handlers (after setting transient), health_update (after reconciliation)

This keeps logic clean and avoids drift between imperative updates.

---

## 4. Transition Row: First-Class Operator Feedback Channel

Not just helper text. This row is the **operator feedback channel**—the single place the operator looks to understand what the system is doing.

**Examples:**

| Transient state | Main message | Subtext (optional) |
|-----------------|--------------|--------------------|
| stoppingRecording | Finalizing MP4 and stopping camera process… | — |
| stoppingSession | Stopping session… | Finalizing recording and ending telemetry capture |
| startingRecording | Starting recording… | — |
| startingSession | Starting session… | — |
| Timeout (stopping) | Stop may have failed | Check connection and retry. [Refresh status] |
| Idle | — | (empty or contextual, e.g. "Ready to record") |

**Distinguish session-stop from recording-stop:** When stopping session, explicitly say that recording is being finalized. Subtext: "Finalizing recording and ending telemetry capture."

**Implementation:** Dedicated element `#operations-transition-row` with:
- Primary message (bold or prominent)
- Optional subtext (muted, smaller)
- Refresh affordance when in timeout state

---

## 5. REC Timer Visibility

Show elapsed timer when:
- Recording is **actually active** (backend says so), OR
- **Optimistically stopping** (user clicked stop, backend not yet confirmed)

Keep the timer visible until backend confirms stop. That preserves context and makes the transition feel continuous instead of abruptly blank.

---

## 6. Timeout Handling

**Include it.** 12–15 second timeout with:
- Warning state (e.g. amber/muted styling)
- Retry suggestion in transition row
- "Refresh status" affordance (e.g. button or link that clears transient and refetches /connection/state or triggers a health refresh)

**Logic:** On each health_update, if `stoppingSessionSince` or `stoppingRecordingSince` is set and `(Date.now() - since) > 15000`, transition to timeout state. Show message + Refresh affordance. Clear transient on Refresh click.

---

## 7. Phased Implementation Order

### Phase 1 (Biggest UX gain fastest)

1. Transient state object (with timestamps)
2. Immediate disable + derived label + spinner on click
3. Reconciliation from health_update
4. Transition message row (first-class status area)
5. Timeout handling (12–15s, warning, Refresh affordance)

### Phase 2

1. 4-block HUD strip (Connection, Session, Camera, Recording)
2. REC pill (red, animate-pulse when active)
3. Elapsed timer (visible when recording active or optimistically stopping)
4. Latest recording tile

### Phase 3

1. Visual polish and spacing rhythm
2. Stronger card styling
3. Optional compact session summary row

---

## 8. Files to Change

| File | Changes |
|------|---------|
| [src/airautomatica/ui/templates/dashboard.html](src/airautomatica/ui/templates/dashboard.html) | Operations card HTML, CSS, JS: transient state, derived rendering, transition row, timeout, then HUD strip, REC pill, timer |

---

## 9. Explicit Avoid

**Do not wait for backend changes.** Frontend optimism plus reconciliation is enough to solve the immediate UX problem. Backend async stop (202 + background task) remains an optional later improvement.

---

## 10. Concept A Confirmed

Compact Operator Panel is the right first target. Fits current layout and can be implemented incrementally without tearing up the whole page. Better to land a good version than overdesign a fancy one.
