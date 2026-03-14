# AI HAT Scope Professional Cleanup — Summary

## What Was Changed and Why

### 1. Subsystem Definition and Scope

- **Created** [docs/ai_hat_scope.md](ai_hat_scope.md): Subsystem definition, current capability, not-yet/out-of-scope, relation to companion computer and flight controller, AI HAT vs persisted detections table.

### 2. Glossary and Roadmap

- **Added** to ai_hat_scope.md: Glossary (AI HAT, AI HAT+, Hailo-8L, one-shot, last one-shot, persisted history, structured detections, normalized events, threshold, diagnostics, perception).
- **Added** to ai_hat_scope.md: Phased roadmap (A: Capability — implemented; B: One-shot — implemented; C: Usability — implemented; D: Future — not implemented).

### 3. Documentation Cleanup

- **Rewrote** [docs/ai_hat.md](ai_hat.md): Professional structure, clearer API table, cached vs persisted section, config flags table, limitations, near-term next steps.
- **Updated** [README.md](../README.md): AI HAT hardware row now reflects real Hailo integration; removed "scaffolded only" and "not yet implemented."
- **Updated** [docs/dashboard.md](dashboard.md): Added AI HAT section; clarified Recent Detections as persisted mission-flow; distinguished from AI HAT one-shot.
- **Updated** [docs/hardware_hookup.md](hardware_hookup.md): AI HAT vs Ollama table reflects current one-shot capability.
- **Updated** [docs/example_hardware.md](example_hardware.md): Removed "scaffolded only"; reflects AI HAT one-shot support.

### 4. UI Wording and Grouping

- **AI HAT section** (dashboard): Added subtitle "Companion-side perception. One-shot detection. Not flight-critical."
- **Button**: Renamed "Run AI Detection Test" → "Run one-shot detection" with tooltip.
- **Settings**: "AI HAT detection threshold" → "AI HAT one-shot threshold" with clearer help text.

### 5. API Semantics

- **GET /api/ai/status**: Docstring clarified: "Capability and current config/readiness. Not health."
- **GET /api/ai/diagnostics**: Docstring clarified: "Deep troubleshooting."
- **POST /api/ai/detect**: Docstring clarified: "Execute one-shot detection."
- **GET /api/ai/last-detection**: Docstring clarified: "Cached result of the most recent successful one-shot detection."
- **Diagnostics**: Added `detection_threshold` to object_detection block.

### 6. Boundaries Preserved

- AI HAT optional
- AI HAT != flight control
- One-shot != persisted history
- Diagnostics != health
- /health not touched

## Files Modified

- docs/ai_hat_scope.md (new)
- docs/ai_hat.md (rewritten)
- docs/ai_hat_cleanup_summary.md (new)
- docs/dashboard.md
- docs/hardware_hookup.md
- docs/example_hardware.md
- README.md
- src/airautomatica/api/routers/ai.py
- src/airautomatica/ui/templates/dashboard.html
