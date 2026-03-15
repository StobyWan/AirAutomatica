<template>
  <div class="p-4 w-full max-w-3xl mx-auto">
    <h1 class="flex items-center gap-1 mb-2">
      <span class="text-connecting shrink-0">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 512 512"
          role="img"
          aria-label="AirAutomatica logo"
          class="h-10 w-10"
        >
          <title>AirAutomatica</title>
          <g fill="currentColor">
            <path d="M56 252 L210 168 L242 186 L144 252 L242 326 L210 344 Z" />
            <path d="M456 252 L302 168 L270 186 L368 252 L270 326 L302 344 Z" />
            <path d="M256 86 L374 404 H324 L294 334 H218 L188 404 H138 Z M237 284 H275 L256 226 Z" />
            <rect x="208" y="284" width="96" height="32" rx="16" />
          </g>
        </svg>
      </span>
      <span class="text-2xl font-bold">AIRAUTOMATICA</span>
    </h1>
    <h2 class="text-muted font-normal text-base mb-4">Connection Setup</h2>
    <p class="text-[var(--text)]/80 text-sm mb-6">
      Choose how to connect to your flight controller or continue in mock mode.
    </p>
    <p class="text-muted text-xs mb-4">
      No hardware? Continue in Mock Mode to develop without a flight controller.
    </p>

    <div v-if="connectionStore.error" class="mb-4 p-3 rounded-lg bg-disconnected/20 text-disconnected text-sm">
      {{ connectionStore.error }}
      <button
        type="button"
        class="ml-2 underline"
        @click="connectionStore.clearError"
      >
        Dismiss
      </button>
    </div>

    <div class="flex flex-col md:flex-row md:items-start gap-6 mb-6">
      <div class="flex flex-col gap-2 w-full md:flex-[1.5] md:min-w-0">
        <button
          type="button"
          class="landing-btn landing-btn-primary w-full"
          :disabled="connectionStore.loading"
          @click="onAutoDetect"
        >
          {{ connectionStore.loading ? 'Detecting…' : 'Auto Detect' }}
        </button>
        <button
          type="button"
          class="landing-btn landing-btn-secondary w-full"
          :disabled="connectionStore.loading"
          @click="onSetMode('ardupilot')"
        >
          Use ArduPilot
        </button>
        <button
          type="button"
          class="landing-btn landing-btn-secondary w-full"
          :disabled="connectionStore.loading"
          @click="onSetMode('inav')"
        >
          Use iNav
        </button>
        <button
          type="button"
          class="landing-btn landing-btn-secondary w-full"
          :disabled="connectionStore.loading"
          @click="onSetMode('mock')"
        >
          Mock Mode
        </button>
      </div>

      <div class="w-full md:flex-[1.25] md:min-w-0">
        <DetectedPortsPanel
          :ports="connectionStore.ports"
          :ports-loading="connectionStore.portsLoading"
          :ports-error="connectionStore.portsError"
          @retry="connectionStore.fetchPorts"
        />
      </div>
    </div>

    <div v-if="connectionStore.detectionResult" class="card text-sm">
      <h3 class="text-muted text-xs font-semibold mb-2">Detection result</h3>
      <pre class="text-xs overflow-auto">{{ connectionStore.detectionResult }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useConnectionStore } from '@/stores/connection'
import { useSocket } from '@/composables/useSocket'
import DetectedPortsPanel from '@/components/DetectedPortsPanel.vue'
import type { PortInfo } from '@/types'

const router = useRouter()
const connectionStore = useConnectionStore()
const { socket } = useSocket()

const dashboardPath = (import.meta.env.VITE_BASE_PATH || '').replace(/\/$/, '')
  ? ''
  : '/dashboard'

function handlePortsUpdate(payload: { ports: PortInfo[] }) {
  connectionStore.updatePortsFromSocket(payload)
}

onMounted(async () => {
  connectionStore.fetchPorts()
  socket.on('ports_update', handlePortsUpdate)
  await connectionStore.fetchState()
  if (connectionStore.connectionState !== 'setup') {
    router.replace(dashboardPath || '/')
  }
})

onBeforeUnmount(() => {
  socket.off('ports_update', handlePortsUpdate)
})

async function onAutoDetect() {
  try {
    await connectionStore.detect()
    router.push(dashboardPath || '/')
  } catch {
    // Error shown in store
  }
}

async function onSetMode(mode: 'mock' | 'ardupilot' | 'inav') {
  try {
    await connectionStore.setMode(mode)
    router.push(dashboardPath || '/')
  } catch {
    // Error shown in store
  }
}
</script>

<style scoped>
.landing-btn {
  @apply block py-3 px-4 rounded-lg text-[0.9375rem] font-medium cursor-pointer transition-colors text-center;
}
.landing-btn:disabled {
  @apply opacity-60 cursor-not-allowed;
}
.landing-btn-primary {
  background: var(--connecting);
  color: #fff;
  border: 1px solid transparent;
}
.landing-btn-primary:hover:not(:disabled) {
  background: #2563eb;
}
.landing-btn-secondary {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text);
  border: 1px solid rgba(255, 255, 255, 0.2);
}
.landing-btn-secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
}
</style>
