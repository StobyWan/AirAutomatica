<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <h2 class="text-base font-semibold text-slate-200 mb-3">Operations</h2>

    <p class="text-sm text-slate-400 mb-3">
      {{ sessionStatusText }}
    </p>

    <div class="operations-hud-strip grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
      <div class="operations-hud-block rounded-lg border border-slate-700 bg-slate-800/50 p-3">
        <div class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Connection</div>
        <span
          class="operations-chip inline-flex items-center gap-0.25 px-2 py-0.5 rounded-md text-xs font-semibold"
          :class="connectionChipClass"
        >
          {{ connectionChipText }}
        </span>
      </div>
      <div class="operations-hud-block rounded-lg border border-slate-700 bg-slate-800/50 p-3">
        <div class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Session</div>
        <div class="flex items-center gap-2 flex-wrap">
          <span v-if="connectionStore.sessionId" class="text-cyan-400 font-mono text-sm">
            #{{ connectionStore.sessionId }}
          </span>
          <span v-else class="text-slate-500 text-sm">Idle</span>
          <button
            v-if="!connectionStore.sessionId && canStartSession"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium disabled:opacity-50"
            :disabled="opsLoading || startingSession"
            @click="handleStartSession"
          >
            {{ startingSession ? 'Starting…' : 'Start Session' }}
          </button>
          <button
            v-if="connectionStore.sessionId"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-amber-900/30 hover:bg-amber-800/40 text-amber-200 text-sm font-medium border border-amber-700/50 disabled:opacity-50"
            :disabled="opsLoading || stoppingSession"
            @click="handleStopSession"
          >
            {{ stoppingSession ? 'Stopping…' : 'Stop Session' }}
          </button>
        </div>
      </div>
      <div class="operations-hud-block rounded-lg border border-slate-700 bg-slate-800/50 p-3">
        <div class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Camera</div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            role="switch"
            :aria-checked="cameraReady"
            class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900"
            :class="cameraReady ? 'bg-cyan-600' : 'bg-slate-600'"
            @click="toggleCameraReady"
          >
            <span
              class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
              :class="cameraReady ? 'translate-x-5' : 'translate-x-0.5'"
            />
          </button>
          <span class="text-sm text-slate-400">{{ cameraReady ? 'Ready' : 'Not ready' }}</span>
        </div>
      </div>
      <div class="operations-hud-block rounded-lg border border-slate-700 bg-slate-800/50 p-3">
        <div class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Recording</div>
        <div class="flex items-center gap-2 flex-wrap">
          <span
            class="operations-chip inline-flex items-center gap-0.25 px-2 py-0.5 rounded-md text-xs font-semibold"
            :class="recordingChipClass"
          >
            {{ recordingChipText }}
          </span>
          <span v-if="recordingTimer" class="text-xs font-mono text-slate-400">{{ recordingTimer }}</span>
          <button
            v-if="cameraRecording && !stoppingRecording"
            type="button"
            class="px-2 py-1 rounded text-xs font-medium bg-red-900/30 text-red-300 hover:bg-red-800/40 border border-red-800/50 disabled:opacity-50"
            :disabled="opsLoading"
            @click="handleStopRecording"
          >
            Stop
          </button>
          <button
            v-else-if="connectionStore.sessionId && cameraRecordingAvailable && !cameraRecording"
            type="button"
            class="px-2 py-1 rounded text-xs font-medium bg-cyan-600/20 text-cyan-300 hover:bg-cyan-500/30 disabled:opacity-50"
            :disabled="opsLoading"
            @click="handleStartRecording"
          >
            Start
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="transitionRowVisible"
      class="mt-3 px-4 py-3 rounded-lg border text-sm"
      :class="transitionRowClass"
    >
      {{ transitionRowText }}
    </div>

    <div
      v-if="opsError"
      class="mt-3 px-4 py-3 rounded-lg border border-red-800/50 bg-red-950/30 text-red-200 text-sm"
    >
      {{ opsError }}
      <button
        type="button"
        class="ml-2 text-xs text-red-300 hover:text-red-100 underline"
        @click="opsError = ''"
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
import * as sessionApi from '@/api/session'
import * as cameraApi from '@/api/camera'
import { recordingsUrl } from '@/config'
import { labelMode } from '@/utils/formatters'

const connectionStore = useConnectionStore()
const healthStore = useHealthStore()

const opsLoading = ref(false)
const startingSession = ref(false)
const stoppingSession = ref(false)
const stoppingRecording = ref(false)
const timerTick = ref(0)
const opsError = ref('')

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
  if (connectionStore.sessionId) {
    return `Session active #${connectionStore.sessionId}`
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
  if (stoppingRecording.value) return 'Stopping…'
  if (cameraRecording.value) return 'REC'
  return 'Idle'
})

const recordingChipClass = computed(() => {
  if (stoppingRecording.value || cameraRecording.value) {
    return 'bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse'
  }
  return 'bg-slate-600/30 text-slate-400 border border-slate-500/40'
})

const recordingTimer = computed(() => {
  void timerTick.value
  const startedAt = healthStore.lastHealth?.camera_recording_started_at
  if (!startedAt || (!cameraRecording.value && !stoppingRecording.value)) return ''
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
  () => startingSession.value || stoppingSession.value
)

const transitionRowText = computed(() => {
  if (startingSession.value) return 'Starting session…'
  if (stoppingSession.value) return 'Stopping session…'
  return ''
})

const transitionRowClass = computed(() => {
  if (stoppingSession.value) {
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
  opsError.value = ''
  try {
    await cameraApi.postCameraReady(next)
    healthStore.patchHealth({ camera_ready: next })
  } catch (e) {
    opsError.value = e instanceof Error ? e.message : 'Failed to set camera ready'
  }
}

async function handleStartSession() {
  startingSession.value = true
  opsLoading.value = true
  opsError.value = ''
  try {
    await sessionApi.startSession()
    await connectionStore.fetchState()
  } catch (e) {
    opsError.value = e instanceof Error ? e.message : 'Failed to start session'
  } finally {
    startingSession.value = false
    opsLoading.value = false
  }
}

async function handleStopSession() {
  stoppingSession.value = true
  opsLoading.value = true
  opsError.value = ''
  try {
    await sessionApi.stopSession()
    await connectionStore.fetchState()
  } catch (e) {
    opsError.value = e instanceof Error ? e.message : 'Failed to stop session'
  } finally {
    stoppingSession.value = false
    opsLoading.value = false
  }
}

async function handleStartRecording() {
  opsLoading.value = true
  opsError.value = ''
  try {
    await cameraApi.startRecording()
  } catch (e) {
    opsError.value = e instanceof Error ? e.message : 'Failed to start recording'
  } finally {
    opsLoading.value = false
  }
}

async function handleStopRecording() {
  stoppingRecording.value = true
  opsLoading.value = true
  opsError.value = ''
  try {
    await cameraApi.stopRecording()
  } catch (e) {
    opsError.value = e instanceof Error ? e.message : 'Failed to stop recording'
  } finally {
    stoppingRecording.value = false
    opsLoading.value = false
  }
}

onMounted(() => {
  recordingTimerInterval = setInterval(() => {
    if (
      (cameraRecording.value || stoppingRecording.value) &&
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
