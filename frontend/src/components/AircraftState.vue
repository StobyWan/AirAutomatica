<template>
  <div class="flex flex-col sm:flex-row gap-4">
    <!-- Compass -->
    <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-3 w-[136px] min-w-[136px] max-w-[136px]">
      <h3 class="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Compass</h3>
      <div class="relative w-20 h-20 mx-auto rounded-full border border-slate-600 bg-slate-900/80 flex items-center justify-center shrink-0">
        <span class="absolute -top-0.5 left-1/2 -translate-x-1/2 text-[10px] font-semibold text-slate-500">N</span>
        <div
          class="absolute inset-0 flex items-center justify-center pointer-events-none transition-transform duration-150"
          :style="{ transform: `rotate(${headingDeg}deg)` }"
        >
          <svg class="w-8 h-8 text-cyan-400" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L4 22h4l4-8 4 8h4L12 2z" />
          </svg>
        </div>
      </div>
      <div class="mt-1.5 text-center text-sm font-mono text-slate-300">
        {{ headingText }}
      </div>
    </div>

    <!-- State fields -->
    <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-3 flex-1 min-w-0">
      <h3 class="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">State</h3>
      <div class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div class="flex justify-between">
          <span class="text-slate-500">Mode</span>
          <span class="font-mono text-slate-300">{{ stateStore.lastState?.mode ?? '—' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">Armed</span>
          <span class="font-mono text-slate-300">{{ stateStore.lastState?.armed ? 'Yes' : 'No' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">Connected</span>
          <span class="font-mono text-slate-300">{{ stateStore.lastState?.connected ? 'Yes' : 'No' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">GPS fix</span>
          <span class="font-mono text-slate-300">{{ gpsFixText }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">Sats</span>
          <span class="font-mono text-slate-300">{{ stateStore.lastState?.satellites_visible ?? '—' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">Heartbeat</span>
          <span class="font-mono text-slate-300">{{ heartbeatText }}</span>
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
</script>
