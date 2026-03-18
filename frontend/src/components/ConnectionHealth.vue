<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <div class="flex items-center justify-between gap-4 mb-2 flex-wrap">
      <h2 class="text-base font-semibold text-slate-200 m-0">Connection & Health</h2>
      <router-link
        v-if="sessionId"
        :to="{ name: 'SessionDetail', params: { id: String(sessionId) } }"
        class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-sm transition-colors"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
        View current session
      </router-link>
    </div>

    <div class="text-sm text-slate-300">
      <span class="text-slate-500">Telemetry:</span>
      {{ healthStore.lastHealth?.telemetry_backend ?? '—' }}
    </div>
    <div v-if="sessionId" class="mt-2 text-sm text-slate-300">
      <span class="text-slate-500">Session:</span>
      #{{ sessionId }}
    </div>

    <details class="mt-3">
      <summary class="text-xs text-slate-400 cursor-pointer hover:text-slate-300 select-none">
        View details
      </summary>
      <div v-if="capabilities" class="mt-2 pt-2 border-t border-slate-600/50">
        <h3 class="text-xs font-semibold text-slate-400 mb-1.5">Autopilot Capabilities</h3>
        <div class="flex flex-wrap gap-1.5 text-xs">
          <span
            v-for="(v, k) in capabilityChips"
            :key="k"
            class="inline-flex px-2 py-0.5 rounded font-medium"
            :class="v ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-red-500/20 text-red-400 border border-red-500/40'"
          >
            {{ capabilityLabels[k] ?? k }} {{ v ? '✓' : '✗' }}
          </span>
        </div>
        <p v-if="capabilities.firmware_name" class="text-sm text-slate-300 mt-1.5">
          {{ capabilities.firmware_name }}
          <span v-if="capabilities.profile_id" class="text-slate-500">({{ capabilities.profile_id }})</span>
        </p>
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-2">
        <div
          v-for="([label, value]) in healthFields"
          :key="String(label)"
          class="field"
        >
          <label class="text-xs text-slate-500">{{ label }}</label>
          <span class="text-sm font-mono text-slate-300 block">{{ value ?? '—' }}</span>
        </div>
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-2">
        <div
          v-for="([label, value]) in sessionFields"
          :key="String(label)"
          class="field"
        >
          <label class="text-xs text-slate-500">{{ label }}</label>
          <span class="text-sm font-mono text-slate-300 block">{{ value ?? '—' }}</span>
        </div>
      </div>
    </details>

    <div class="mt-3 pt-3 border-t border-slate-600/50">
      <h3 class="text-xs font-semibold text-slate-400 mb-1.5">AI HAT (optional)</h3>
      <p class="text-[10px] text-slate-500 mb-2">Companion-side perception. One-shot detection. Not flight-critical.</p>
      <div v-if="activeCameraLabel" class="text-xs text-slate-500 mb-2">
        Active camera: {{ activeCameraLabel }}
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-if="!cameraRecording"
          type="button"
          class="px-3 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-slate-200 text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="aiDetectDisabled"
          :title="aiDetectDisabled ? 'Camera busy or still capture unavailable' : 'Capture one frame and run Hailo inference'"
          @click="runAiDetect"
        >
          Run one-shot detection
        </button>
        <span v-if="aiDetectLoading" class="text-xs text-slate-400">Running…</span>
      </div>
      <div v-if="aiDetectResult" class="mt-2 text-xs" :class="aiDetectError ? 'text-amber-400' : 'text-slate-400'">
        {{ aiDetectResult }}
      </div>
      <div v-if="lastDetection" class="mt-1.5 text-xs text-slate-500">
        {{ lastDetection }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useHealthStore } from '@/stores/health'
import { useConnectionStore } from '@/stores/connection'
import { aiDetect, getLastDetection } from '@/api/ai'

const healthStore = useHealthStore()
const connectionStore = useConnectionStore()

const aiDetectLoading = ref(false)
const aiDetectResult = ref('')
const lastDetection = ref('')

const sessionId = computed(() => connectionStore.liveSessionId)

const cameraRecording = computed(
  () => healthStore.lastHealth?.camera_recording === true
)

const stillCaptureAvailable = computed(
  () => healthStore.lastHealth?.still_capture_available === true
)

const activeCameraLabel = computed(
  () => healthStore.lastHealth?.active_camera_label ?? null
)

const aiDetectDisabled = computed(
  () => aiDetectLoading.value || cameraRecording.value || !stillCaptureAvailable.value
)

const aiDetectError = computed(() => {
  const r = aiDetectResult.value
  return r && (r.includes('error') || r.includes('failed') || r.includes('Error'))
})

const capabilities = computed(() => {
  const caps = healthStore.lastHealth?.capabilities as Record<string, unknown> | undefined
  return caps ?? null
})

const capabilityLabels: Record<string, string> = {
  supports_params_read: 'params_read',
  supports_params_write: 'params_write',
  supports_command_long: 'command_long',
  supports_message_interval: 'message_interval',
  supports_missions: 'missions',
  supports_guided_actions: 'guided',
  supports_rc_over_mavlink: 'rc_over_mavlink',
}

const capabilityChips = computed(() => {
  const caps = capabilities.value
  if (!caps) return {}
  const out: Record<string, boolean> = {}
  for (const k of Object.keys(capabilityLabels)) {
    out[k] = caps[k] === true
  }
  return out
})

const healthFields = computed(() => {
  const h = healthStore.lastHealth
  const tel = (h?.telemetry as Record<string, unknown>) ?? {}
  return [
    ['telemetry_backend', h?.telemetry_backend],
    ['ai_mode', h?.ai_mode],
    ['heartbeat_age_s', tel.heartbeat_age_s != null ? `${Number(tel.heartbeat_age_s).toFixed(1)} s` : null],
    ['reconnect_count', tel.reconnect_count],
    ['last_disconnect_reason', tel.last_disconnect_reason],
  ]
})

const sessionFields = computed(() => {
  const h = healthStore.lastHealth
  const p = (h?.persistence as Record<string, unknown>) ?? {}
  return [
    ['session_id', h?.session_id],
    ['persistence_enabled', p.persistence_enabled],
    ['last_persistence_error', p.last_persistence_error],
  ]
})

async function runAiDetect() {
  aiDetectLoading.value = true
  aiDetectResult.value = ''
  try {
    const res = await aiDetect()
    if (res.errors?.length) {
      aiDetectResult.value = res.errors.join('; ')
    } else if (res.detections?.length) {
      aiDetectResult.value = `Detected: ${res.detections.map((d) => d.label).join(', ')}`
    } else {
      aiDetectResult.value = 'No detections'
    }
    const last = await getLastDetection()
    if (last && typeof last === 'object') {
      const d = last as { label?: string; summary?: string }
      lastDetection.value = d.summary ?? (d.label ? `${d.label} (cached)` : '')
    }
  } catch (e) {
    aiDetectResult.value = e instanceof Error ? e.message : 'Detection failed'
    lastDetection.value = ''
  } finally {
    aiDetectLoading.value = false
  }
}
</script>
