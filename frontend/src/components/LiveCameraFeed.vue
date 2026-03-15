<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <h2 class="text-base font-semibold text-slate-200 mb-3">Live Camera</h2>

    <div class="relative aspect-video rounded bg-slate-900/50 overflow-hidden">
      <div
        v-if="!cameraAvailable"
        class="absolute inset-0 flex items-center justify-center"
      >
        <p class="text-slate-500 text-sm">Camera not available</p>
      </div>

      <div
        v-else-if="!cameraReady"
        class="absolute inset-0 flex items-center justify-center"
      >
        <p class="text-slate-500 text-sm">Turn on Camera Ready in Operations to view live feed</p>
      </div>

      <div v-else class="absolute inset-0 bg-black">
        <img
          :src="previewUrl"
          class="w-full h-full object-contain"
          alt="Live camera preview"
          @load="previewError = null"
          @error="onPreviewError"
        />
        <p
          v-if="previewError"
          class="absolute inset-0 flex items-center justify-center bg-slate-900/80 text-slate-400 text-sm"
        >
          {{ previewError }}
        </p>
      </div>

      <div
        v-if="cameraReady"
        class="absolute inset-0 pointer-events-none flex items-start justify-start p-2"
      >
        <div class="bg-black/60 text-white font-mono text-xs px-2 py-1 rounded">
          Mode: {{ hud.mode }} | Alt: {{ hud.alt }}m | Spd: {{ hud.spd }}m/s | Batt: {{ hud.batt }}V | Armed: {{ hud.armed }} | Sats: {{ hud.sats }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useHealthStore } from '@/stores/health'
import { useStateStore } from '@/stores/state'
import { API_BASE } from '@/config'
import type { AircraftState } from '@/types'

const healthStore = useHealthStore()
const stateStore = useStateStore()

const cameraRecording = computed(
  () => healthStore.lastHealth?.camera_recording === true
)

const cameraAvailable = computed(
  () => healthStore.lastHealth?.camera_recording_available !== false
)

const cameraReady = computed(
  () => healthStore.lastHealth?.camera_ready === true
)

const hud = computed(() => formatTelemetryHud(stateStore.lastState))

function formatTelemetryHud(state: AircraftState | null): {
  mode: string
  alt: string
  spd: string
  batt: string
  armed: string
  sats: string
} {
  const dash = '—'
  if (!state) {
    return { mode: dash, alt: dash, spd: dash, batt: dash, armed: dash, sats: dash }
  }
  return {
    mode: state.mode || dash,
    alt: state.rel_alt_m != null ? state.rel_alt_m.toFixed(1) : dash,
    spd: state.groundspeed_m_s != null ? state.groundspeed_m_s.toFixed(1) : dash,
    batt: state.voltage_v != null ? state.voltage_v.toFixed(1) : dash,
    armed: state.armed ? 'YES' : 'NO',
    sats: state.satellites_visible != null ? String(state.satellites_visible) : dash,
  }
}

const previewUrl = computed(() => {
  const base = String(API_BASE ?? '').replace(/\/$/, '')
  const path = cameraRecording.value ? '/camera/recording/stream' : '/camera/preview/stream'
  return base ? `${base}${path}` : path
})

const previewError = ref<string | null>(null)

function onPreviewError() {
  previewError.value = cameraRecording.value
    ? 'Camera recording — preview unavailable'
    : 'Unable to load preview'
}
</script>
