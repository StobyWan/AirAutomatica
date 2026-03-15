<template>
  <div class="flex flex-col sm:flex-row gap-4">
    <!-- Compass -->
    <div class="rounded-lg border border-slate-600/80 bg-slate-800/60 p-4 flex-1 min-w-[136px]">
      <h3 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">Compass</h3>
      <div class="relative w-20 h-20 mx-auto rounded-full border-2 border-slate-600/80 bg-slate-900/90 flex items-center justify-center shrink-0 shadow-inner">
        <span class="absolute -top-0.5 left-1/2 -translate-x-1/2 text-[10px] font-bold text-slate-500">N</span>
        <div
          class="absolute inset-0 flex items-center justify-center pointer-events-none transition-transform duration-150"
          :style="{ transform: `rotate(${headingDeg}deg)` }"
        >
          <svg class="w-8 h-8 text-cyan-400 drop-shadow-sm" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L4 22h4l4-8 4 8h4L12 2z" />
          </svg>
        </div>
      </div>
      <div class="mt-2 text-center text-sm font-mono font-medium text-slate-200 tabular-nums">
        {{ headingText }}
      </div>
    </div>

    <!-- State fields -->
    <div class="rounded-lg border border-slate-600/80 bg-slate-800/60 p-4 flex-1 min-w-0">
      <h3 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">State</h3>
      <div class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Mode</span>
          <span class="font-mono text-slate-200 font-medium truncate">{{ stateStore.lastState?.mode ?? '—' }}</span>
        </div>
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Armed</span>
          <span class="font-mono font-medium" :class="armedClass">{{ stateStore.lastState?.armed ? 'Yes' : 'No' }}</span>
        </div>
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Connected</span>
          <span class="font-mono font-medium" :class="connectedClass">{{ stateStore.lastState?.connected ? 'Yes' : 'No' }}</span>
        </div>
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">GPS fix</span>
          <span class="font-mono font-medium" :class="gpsFixClass">{{ gpsFixText }}</span>
        </div>
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Sats</span>
          <span class="font-mono font-medium tabular-nums" :class="satsClass">{{ stateStore.lastState?.satellites_visible ?? '—' }}</span>
        </div>
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Heartbeat</span>
          <span class="font-mono font-medium tabular-nums" :class="heartbeatClass">{{ heartbeatText }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStateStore } from '@/stores/state'

const stateStore = useStateStore()

const headingDeg = computed(() => {
  const h = stateStore.lastState?.heading_deg
  if (h == null || !Number.isFinite(h)) return 0
  return h
})

const headingText = computed(() => {
  const h = stateStore.lastState?.heading_deg
  if (h == null || !Number.isFinite(h)) return '—'
  return `${Math.round(h)}°`
})

const gpsFixText = computed(() => {
  const fix = stateStore.lastState?.gps_fix_type
  if (fix == null) return '—'
  if (fix >= 3) return '3D'
  if (fix >= 2) return '2D'
  if (fix === 1) return 'no fix'
  return String(fix)
})

const heartbeatText = computed(() => {
  const age = stateStore.lastState?.heartbeat_age_s
  if (age == null || !Number.isFinite(age)) return '—'
  return age.toFixed(1) + ' s'
})

const armedClass = computed(() =>
  stateStore.lastState?.armed ? 'text-emerald-400' : 'text-amber-500/90'
)

const connectedClass = computed(() =>
  stateStore.lastState?.connected ? 'text-emerald-400' : 'text-red-400/90'
)

const gpsFixClass = computed(() => {
  const fix = stateStore.lastState?.gps_fix_type
  if (fix == null) return 'text-slate-400'
  if (fix >= 3) return 'text-emerald-400'
  if (fix >= 2) return 'text-amber-500/90'
  return 'text-red-400/90'
})

const satsClass = computed(() => {
  const s = stateStore.lastState?.satellites_visible
  if (s == null || typeof s !== 'number') return 'text-slate-400'
  if (s >= 8) return 'text-emerald-400'
  if (s >= 4) return 'text-amber-500/90'
  return 'text-red-400/90'
})

const heartbeatClass = computed(() => {
  const age = stateStore.lastState?.heartbeat_age_s
  if (age == null || !Number.isFinite(age)) return 'text-slate-400'
  if (age < 1) return 'text-emerald-400'
  if (age < 2) return 'text-amber-500/90'
  return 'text-red-400/90'
})
</script>
