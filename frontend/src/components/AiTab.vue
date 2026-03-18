<template>
  <div class="space-y-4">
    <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h2 class="text-base font-semibold text-slate-200 mb-2">Recent Detections</h2>
      <p class="text-xs text-slate-500 mb-3">
        Mission-flow (Ollama/mock), AI HAT recording-time, and one-shot (aihat) when session active. Source shown per card.
      </p>
      <div
        v-if="detectionsStore.detections.length"
        class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-64 overflow-y-auto"
      >
        <div
          v-for="(d, i) in detectionsStore.detections"
          :key="i"
          class="p-3 rounded-lg bg-slate-800/40 border border-slate-700/50 text-sm"
        >
          <div class="font-medium text-slate-200">{{ d.label }}</div>
          <div class="text-slate-400 text-xs mt-0.5">
            {{ formatConf(d.confidence) }}
            <span v-if="d.source_backend" class="ml-1">· {{ fmtSourceBackend(d.source_backend).text }}</span>
          </div>
          <p v-if="d.summary" class="text-slate-400 text-xs mt-1">{{ d.summary }}</p>
        </div>
      </div>
      <p v-else class="py-6 text-center text-slate-500 text-sm">
        No detections yet. Start a session and run AI HAT or mission-flow to see results.
      </p>
    </div>

    <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h2 class="text-base font-semibold text-slate-200 mb-3">One-shot detection</h2>
      <p class="text-xs text-slate-500 mb-2">Capture one frame from the active camera and run Hailo inference.</p>
      <div v-if="activeCameraLabel" class="text-xs text-slate-500 mb-2">Active camera: {{ activeCameraLabel }}</div>
      <button
        type="button"
        class="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="oneShotDisabled"
        @click="runOneShotDetection"
      >
        {{ oneShotLoading ? 'Running…' : 'Run one-shot detection' }}
      </button>
      <div v-if="oneShotResult" class="mt-2 text-sm" :class="oneShotError ? 'text-amber-400' : 'text-slate-300'">
        {{ oneShotResult }}
      </div>
    </div>

    <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h2 class="text-base font-semibold text-slate-200 mb-3">AI Analysis</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <h3 class="text-xs font-semibold text-slate-400 mb-1">Telemetry Summary</h3>
          <p class="text-xs text-slate-500 mb-2">Local AI interpretation of current telemetry (Ollama or mock)</p>
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium disabled:opacity-50"
            :disabled="telemetrySummaryLoading"
            @click="runTelemetrySummary"
          >
            {{ telemetrySummaryLoading ? 'Summarizing…' : 'Summarize' }}
          </button>
          <div class="mt-2 text-sm text-slate-300">
            {{ telemetrySummaryContent }}
          </div>
        </div>
        <div>
          <h3 class="text-xs font-semibold text-slate-400 mb-1">Event Classification</h3>
          <p class="text-xs text-slate-500 mb-2">Local AI analysis of recent system events (Ollama or mock)</p>
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium disabled:opacity-50"
            :disabled="eventClassificationLoading"
            @click="runEventClassification"
          >
            {{ eventClassificationLoading ? 'Classifying…' : 'Classify' }}
          </button>
          <div class="mt-2 text-sm text-slate-300">
            {{ eventClassificationContent }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDetectionsStore } from '@/stores/detections'
import { useHealthStore } from '@/stores/health'
import { aiDetect, getTelemetrySummary, getEventClassification } from '@/api/ai'
import { fmtSourceBackend } from '@/utils/formatters'

const detectionsStore = useDetectionsStore()
const healthStore = useHealthStore()

const oneShotLoading = ref(false)
const oneShotResult = ref('')

const cameraRecording = computed(
  () => healthStore.lastHealth?.camera_recording === true
)
const stillCaptureAvailable = computed(
  () => healthStore.lastHealth?.still_capture_available === true
)
const activeCameraLabel = computed(
  () => healthStore.lastHealth?.active_camera_label ?? null
)
const oneShotDisabled = computed(
  () =>
    oneShotLoading.value ||
    cameraRecording.value ||
    !stillCaptureAvailable.value
)
const oneShotError = computed(() => {
  const r = oneShotResult.value
  return r && (r.includes('error') || r.includes('failed') || r.includes('Error'))
})

async function runOneShotDetection() {
  oneShotLoading.value = true
  oneShotResult.value = ''
  try {
    const res = await aiDetect()
    if (res.errors?.length) {
      oneShotResult.value = res.errors.join('; ')
    } else if (res.detections?.length) {
      oneShotResult.value = `Detected: ${res.detections.map((d) => d.label).join(', ')}`
    } else {
      oneShotResult.value = 'No detections'
    }
    detectionsStore.fetchRecentDetections()
  } catch (e) {
    oneShotResult.value = e instanceof Error ? e.message : 'Detection failed'
  } finally {
    oneShotLoading.value = false
  }
}

const telemetrySummaryLoading = ref(false)
const telemetrySummaryContent = ref('Click Summarize to get AI interpretation')

const eventClassificationLoading = ref(false)
const eventClassificationContent = ref('Click Classify to analyze recent events')

function formatConf(c: number): string {
  return c != null ? (c * 100).toFixed(0) + '%' : '—'
}

async function runTelemetrySummary() {
  telemetrySummaryLoading.value = true
  telemetrySummaryContent.value = 'Summarizing…'
  try {
    const res = await getTelemetrySummary()
    telemetrySummaryContent.value = res.summary ?? 'No summary returned'
  } catch (e) {
    telemetrySummaryContent.value = e instanceof Error ? e.message : 'Summarize failed'
  } finally {
    telemetrySummaryLoading.value = false
  }
}

async function runEventClassification() {
  eventClassificationLoading.value = true
  eventClassificationContent.value = 'Classifying…'
  try {
    const res = await getEventClassification()
    const c = res.classification
    if (c && typeof c === 'object') {
      eventClassificationContent.value = JSON.stringify(c, null, 2)
    } else {
      eventClassificationContent.value = 'No classification returned'
    }
  } catch (e) {
    eventClassificationContent.value = e instanceof Error ? e.message : 'Classify failed'
  } finally {
    eventClassificationLoading.value = false
  }
}
</script>
