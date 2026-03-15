<template>
  <div class="p-4 max-w-xl">
    <h1 class="text-2xl font-bold mb-2">AIRAUTOMATICA</h1>
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

    <div class="flex flex-col items-start gap-2 mb-6">
      <button
        type="button"
        class="landing-btn landing-btn-primary w-full max-w-xs"
        :disabled="connectionStore.loading"
        @click="onAutoDetect"
      >
        {{ connectionStore.loading ? 'Detecting…' : 'Auto Detect' }}
      </button>
      <button
        type="button"
        class="landing-btn landing-btn-secondary w-full max-w-xs"
        :disabled="connectionStore.loading"
        @click="onSetMode('ardupilot')"
      >
        Use ArduPilot
      </button>
      <button
        type="button"
        class="landing-btn landing-btn-secondary w-full max-w-xs"
        :disabled="connectionStore.loading"
        @click="onSetMode('inav')"
      >
        Use iNav
      </button>
      <button
        type="button"
        class="landing-btn landing-btn-secondary w-full max-w-xs"
        :disabled="connectionStore.loading"
        @click="onSetMode('mock')"
      >
        Mock Mode
      </button>
    </div>

    <div v-if="connectionStore.detectionResult" class="card text-sm">
      <h3 class="text-muted text-xs font-semibold mb-2">Detection result</h3>
      <pre class="text-xs overflow-auto">{{ connectionStore.detectionResult }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConnectionStore } from '@/stores/connection'

const router = useRouter()
const connectionStore = useConnectionStore()

const dashboardPath = (import.meta.env.VITE_BASE_PATH || '').replace(/\/$/, '')
  ? ''
  : '/dashboard'

onMounted(async () => {
  await connectionStore.fetchState()
  if (connectionStore.connectionState !== 'setup') {
    router.replace(dashboardPath || '/')
  }
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
