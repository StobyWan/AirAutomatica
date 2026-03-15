<template>
  <div class="flex flex-wrap items-center gap-2 py-2 px-3 rounded-lg border border-slate-700 bg-slate-800/50 mb-4">
    <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">Flight</span>
    <span
      class="flight-status-chip px-2 py-0.5 rounded text-xs font-medium"
      :class="armedChipClass"
    >
      {{ armedText }}
    </span>
    <span
      class="flight-status-chip px-2 py-0.5 rounded text-xs font-medium bg-slate-700/60 text-slate-300"
    >
      {{ modeText }}
    </span>
    <span
      class="flight-status-chip px-2 py-0.5 rounded text-xs font-medium bg-slate-700/60 text-slate-400"
    >
      {{ gpsText }}
    </span>
    <span
      class="flight-status-chip px-2 py-0.5 rounded text-xs font-medium"
      :class="linkChipClass"
    >
      {{ linkText }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStateStore } from '@/stores/state'
import { useHealthStore } from '@/stores/health'

const stateStore = useStateStore()
const healthStore = useHealthStore()

const armedText = computed(() => {
  const armed = stateStore.lastState?.armed
  if (armed === true) return 'ARMED'
  if (armed === false) return 'Disarmed'
  return '—'
})

const armedChipClass = computed(() => {
  const armed = stateStore.lastState?.armed
  if (armed === true) return 'bg-amber-900/60 text-amber-200 border border-amber-700/50'
  if (armed === false) return 'bg-slate-700/60 text-slate-400'
  return 'text-slate-500'
})

const modeText = computed(() => {
  const mode = stateStore.lastState?.mode
  return mode != null && mode !== '' ? mode : '—'
})

const gpsText = computed(() => {
  const s = stateStore.lastState
  const sat = s?.satellites_visible
  const fix = s?.gps_fix_type
  if (sat != null && Number.isFinite(sat)) {
    const fixLabel = fix != null && fix >= 2 ? '3D' : fix === 1 ? 'no fix' : ''
    return fixLabel ? `${sat} sat ${fixLabel}` : `${sat} sat`
  }
  return '—'
})

const linkText = computed(() => {
  const tel = healthStore.lastHealth?.telemetry as Record<string, unknown> | undefined
  const status = stateStore.lastState?.telemetry_status ?? tel?.telemetry_status ?? 'disconnected'
  return String(status)
})

const linkChipClass = computed(() => {
  const status = linkText.value
  if (status === 'connected') return 'bg-emerald-900/40 text-emerald-300'
  if (status === 'stale') return 'bg-amber-900/40 text-amber-300'
  return 'bg-slate-700/60 text-slate-500'
})
</script>
