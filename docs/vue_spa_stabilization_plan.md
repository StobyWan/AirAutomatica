# Vue SPA Stabilization Plan (Refined)

Post-parity refinement plan for the AirAutomatica Vue 3 SPA. Incorporates execution feedback and prioritization refinements.

---

## Execution Order (Refined)

### Phase 1A — Immediate Trust Gains
Execute first. Highest value, lowest risk.

1. **Fix SessionDetail base-path bug** — Use `{ name: 'Dashboard' }` instead of `dashboardPath` string
2. **Fix ConnectionHealth session link** — Use `router.resolve({ name: 'SessionDetail', params: { id } })`
3. **Surface Operations HUD API errors** — Show user-visible feedback for toggleCameraReady, start/stop session, start/stop recording failures
4. **Add BaseSpinner** — Single loading affordance; replace 4+ inline spinners

### Phase 1B — Crash Safety + Consistency
5. **Add ErrorBoundary** — Wrap RouterView; prevent full app crash on component errors
6. **Standardize loading/empty/error state styling** — Consistent padding, muted text, spinner color
7. **Remove dead CSS** — `.status-*`, `.operations-chip-*` in base.css

### Phase 2 — Component Extraction
- **BaseModal** — Consolidate 4 modal instances
- **BaseButton** — Primary, secondary, danger variants
- Clean repeated modal/button markup
- **BaseCard** — Defer until Phase 2 complete; reassess if still clearly worth it

### Phase 3 — Production Hardening
- **API timeout** — Opt-in or endpoint-specific; no aggressive defaults; clear messaging (not silent aborts)
- **Reconnect UX** — Light: subtle banner or chip only; no modal/heavy overlay unless app truly unusable
- **Reconnect refetch** — Validate stores refetch correctly on reconnect
- **CI** — Lint and typecheck enforcement

### Phase 4 — Legacy Retirement ✅ Done
- Legacy templates (`dashboard.html`, `session_detail.html`) and `test_dashboard.py` removed
- Dashboard is Vue SPA–only; see `docs/vue_app_tests.md` for recommended frontend tests

---

## Key Refinements (from feedback)

| Topic | Refinement |
|-------|------------|
| Phase 1 order | Base-path → visible errors → BaseSpinner → ErrorBoundary (everyday trust before crash net) |
| BaseCard | Defer; do BaseModal, BaseSpinner, BaseButton first; reassess BaseCard after |
| Fetch timeouts | Opt-in or endpoint-specific; no aggressive defaults; clear messaging |
| Reconnect UX | Light banner/chip; not modal or heavy overlay |

---

## Legacy Retirement Discipline ✅

**Removed:**
- Legacy templates (`dashboard.html`, `session_detail.html`)
- `get_use_spa_dashboard()` — dashboard is SPA-only
- `tests/test_dashboard.py` — see `docs/vue_app_tests.md` for Vue test recommendations

---

## Files Reference

- Base-path fix: `SessionDetailView.vue`, `ConnectionHealth.vue`
- Operations HUD errors: `OperationsHud.vue`
- BaseSpinner: new `components/ui/BaseSpinner.vue`
- ErrorBoundary: new `components/ErrorBoundary.vue`; wrap in `App.vue`
- Dead CSS: `frontend/src/assets/base.css` lines 36–97
