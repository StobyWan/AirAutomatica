<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <h2 class="text-base font-semibold text-slate-200 mb-3">Operations</h2>

    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
      <div class="flex-1 min-w-0">
        <p class="text-sm text-slate-400">
          {{ sessionStatusText }}
        </p>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <button
          v-if="!connectionStore.liveSessionId && canStartSession"
          type="button"
          class="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium disabled:opacity-50"
          :disabled="operationsStore.startingSession"
          @click="operationsStore.startSession"
        >
          {{ operationsStore.startingSession ? 'Starting…' : 'Start Session' }}
        </button>
        <button
          v-if="connectionStore.liveSessionId"
          type="button"
          class="px-4 py-2 rounded-lg bg-amber-900/30 hover:bg-amber-800/40 text-amber-200 text-sm font-medium border border-amber-700/50 disabled:opacity-50"
          :disabled="operationsStore.stoppingSession"
          @click="operationsStore.stopSession"
        >
          {{ operationsStore.stoppingSession ? 'Stopping…' : 'Stop Session' }}
        </button>
        <span v-if="connectionStore.liveSessionId" class="text-cyan-400 font-mono text-sm">
          #{{ connectionStore.liveSessionId }}
        </span>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2 py-2 border-t border-b border-slate-700/50">
      <h3 class="sr-only">Status</h3>
      <span class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Connection</span>
      <span
        class="operations-chip inline-flex items-center gap-0.25 px-2 py-0.5 rounded-md text-xs font-semibold"
        :class="connectionChipClass"
      >
        {{ connectionChipText }}
      </span>
      <span class="text-slate-600">·</span>
      <span class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Camera</span>
      <button
        type="button"
        role="switch"
        :aria-checked="cameraReady"
        class="relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900"
        :class="cameraReady ? 'bg-cyan-600' : 'bg-slate-600'"
        @click="toggleCameraReady"
      >
        <span
          class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
          :class="cameraReady ? 'translate-x-4' : 'translate-x-0.5'"
        />
      </button>
      <span class="text-xs text-slate-400">{{ cameraReady ? 'Ready' : 'Not ready' }}</span>
      <span class="text-slate-600">·</span>
      <span class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Recording</span>
      <span
        class="operations-chip inline-flex items-center gap-0.25 px-2 py-0.5 rounded-md text-xs font-semibold"
        :class="recordingChipClass"
      >
        {{ recordingChipText }}
      </span>
      <span v-if="recordingTimer" class="text-xs font-mono text-slate-400">{{ recordingTimer }}</span>
      <button
        v-if="cameraRecording && !operationsStore.stoppingRecording"
        type="button"
        class="px-2 py-1 rounded text-xs font-medium bg-red-900/30 text-red-300 hover:bg-red-800/40 border border-red-800/50 disabled:opacity-50"
        :disabled="operationsStore.stoppingRecording"
        @click="operationsStore.stopRecording"
      >
        Stop
      </button>
      <button
        v-else-if="connectionStore.liveSessionId && cameraRecordingAvailable && !cameraRecording"
        type="button"
        class="px-2 py-1 rounded text-xs font-medium bg-cyan-600/20 text-cyan-300 hover:bg-cyan-500/30 disabled:opacity-50"
        :disabled="operationsStore.startingRecording"
        @click="operationsStore.startRecording"
      >
        Start
      </button>
    </div>

    <div
      v-if="transitionRowVisible"
      class="mt-3 px-4 py-3 rounded-lg border text-sm"
      :class="transitionRowClass"
    >
      {{ transitionRowText }}
    </div>

    <div
      v-if="operationsStore.opsError"
      class="mt-3 px-4 py-3 rounded-lg border border-red-800/50 bg-red-950/30 text-red-200 text-sm"
    >
      {{ operationsStore.opsError }}
      <button
        type="button"
        class="ml-2 text-xs text-red-300 hover:text-red-100 underline"
        @click="operationsStore.clearOpsError"
      >
        Dismiss
      </button>
    </div>

    <div
      v-if="latestRecordingFilename"
      class="mt-3 px-3 py-2 rounded-lg border border-slate-700 bg-slate-800/30"
    >
      <div class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Latest recording</div>
      <a
        :href="recordingsUrl(latestRecordingFilename)"
        class="font-mono text-sm text-cyan-400 hover:text-cyan-300 truncate block"
        :download="latestRecordingFilename"
      >
        {{ latestRecordingFilename }}
      </a>
    </div>

    <p class="operations-source mt-3 text-sm font-medium text-slate-200 px-3 py-2 rounded-lg bg-slate-800/40 border border-slate-700/50">
      Source: {{ operationsSourceText }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useConnectionStore } from '@/stores/connection'
import { useHealthStore } from '@/stores/health'
import { useOperationsStore } from '@/stores/operations'
import { recordingsUrl } from '@/config'
import { labelMode } from '@/utils/formatters'

const connectionStore = useConnectionStore()
const healthStore = useHealthStore()
const operationsStore = useOperationsStore()

const timerTick = ref(0)

let recordingTimerInterval: ReturnType<typeof setInterval> | null = null

const canStartSession = computed(() =>
  ['mock_idle', 'connected_ardupilot', 'connected_inav'].includes(
    connectionStore.connectionState
  )
)

const cameraReady = computed(() => healthStore.lastHealth?.camera_ready === true)
const cameraRecording = computed(() => healthStore.lastHealth?.camera_recording === true)
const cameraRecordingAvailable = computed(
  () => healthStore.lastHealth?.camera_recording_available !== false
)

const sessionStatusText = computed(() => {
  if (connectionStore.liveSessionId) {
    return `Session active #${connectionStore.liveSessionId}`
  }
  return 'No active session. Click Start Session to begin recording telemetry and detections.'
})

const connectionChipText = computed(() => {
  const s = connectionStore.connectionStatus
  if (s === 'Connected') return 'Connected'
  if (s === 'Connecting') return 'Connecting'
  return 'Disconnected'
})

const connectionChipClass = computed(() => {
  const s = connectionStore.connectionStatus
  if (s === 'Connected') return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
  if (s === 'Connecting') return 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
  return 'bg-slate-600/30 text-slate-400 border border-slate-500/40'
})

const recordingChipText = computed(() => {
  if (operationsStore.stoppingRecording) return 'Stopping…'
  if (cameraRecording.value) return 'REC'
  return 'Idle'
})

const recordingChipClass = computed(() => {
  if (operationsStore.stoppingRecording || cameraRecording.value) {
    return 'bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse'
  }
  return 'bg-slate-600/30 text-slate-400 border border-slate-500/40'
})

const recordingTimer = computed(() => {
  void timerTick.value
  const startedAt = healthStore.lastHealth?.camera_recording_started_at
  if (!startedAt || (!cameraRecording.value && !operationsStore.stoppingRecording)) return ''
  const elapsedMs = Date.now() - new Date(startedAt).getTime()
  const sec = Math.max(0, Math.floor(elapsedMs / 1000))
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`
})

const latestRecordingFilename = computed(() => {
  const h = healthStore.lastHealth
  if (cameraRecording.value && h?.camera_recording_file) {
    return h.camera_recording_file
  }
  if (h?.camera_recording_last_file) {
    return h.camera_recording_last_file
  }
  return ''
})

const transitionRowVisible = computed(
  () => operationsStore.startingSession || operationsStore.stoppingSession
)

const transitionRowText = computed(() => {
  if (operationsStore.startingSession) return 'Starting session…'
  if (operationsStore.stoppingSession) return 'Stopping session…'
  return ''
})

const transitionRowClass = computed(() => {
  if (operationsStore.stoppingSession) {
    return 'border-amber-700/50 bg-amber-900/10 text-amber-200'
  }
  return 'border-slate-600 bg-slate-800/40 text-slate-300'
})

const operationsSourceText = computed(() => {
  const mode = connectionStore.mode ?? healthStore.lastHealth?.telemetry_backend ?? 'mock'
  const port = healthStore.lastHealth?.source_port ?? connectionStore.detectionResult?.port
  const baud = healthStore.lastHealth?.baud ?? connectionStore.detectionResult?.baud
  const modeLabel = labelMode({
    connection_mode: mode,
    telemetry_backend: String(mode),
  })
  if (mode === 'mock') return modeLabel
  return `${modeLabel} · ${port ?? '—'} · ${baud ?? '—'}`
})

async function toggleCameraReady() {
  const next = !cameraReady.value
  try {
    await operationsStore.setCameraReady(next)
  } catch {
    // Error surfaced in operationsStore.opsError
  }
}

onMounted(() => {
  recordingTimerInterval = setInterval(() => {
    if (
      (cameraRecording.value || operationsStore.stoppingRecording) &&
      healthStore.lastHealth?.camera_recording_started_at
    ) {
      timerTick.value++
    }
  }, 1000)
})

onUnmounted(() => {
  if (recordingTimerInterval) {
    clearInterval(recordingTimerInterval)
    recordingTimerInterval = null
  }
})
</script>
