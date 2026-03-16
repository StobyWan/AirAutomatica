<template>
  <LandingView v-if="connectionStore.connectionState === 'setup'" />
  <div v-else class="p-4">
    <div
      v-if="!connected"
      class="mb-4 px-4 py-2 rounded-lg border border-amber-700/50 bg-amber-900/20 text-amber-200 text-sm font-medium"
    >
      Reconnecting…
    </div>
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <h1 class="flex items-center gap-2 text-xl font-bold text-slate-100 tracking-tight">
        <span class="text-connecting shrink-0" aria-hidden="true">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 512 512"
            role="img"
            aria-label="AirAutomatica logo"
            class="h-8 w-8"
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
        AIRAUTOMATICA Dashboard
        <span v-if="appVersion" class="text-slate-500 font-normal text-sm">v{{ appVersion }}</span>
      </h1>
      <div class="flex items-center gap-2">
        <span
          class="status-badge px-2 py-1 rounded text-sm font-semibold"
          :class="statusClass"
        >
          {{ connectionStore.connectionStatus }}
        </span>
        <button
          type="button"
          class="text-sm px-3 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-slate-200 transition-colors"
          @click="connectionStore.fetchState"
        >
          Retry
        </button>
        <button
          type="button"
          class="text-sm px-3 py-1.5 rounded-lg bg-red-900/30 hover:bg-red-800/40 text-red-200 border border-red-800/50 transition-colors"
          @click="connectionStore.disconnect"
        >
          Disconnect
        </button>
      </div>
    </div>

    <DashboardNav />

    <RouterView />

    <footer class="mt-8 pt-4 border-t border-white/10 text-center text-sm text-slate-500">
      AirAutomatica
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DashboardNav from '@/components/DashboardNav.vue'
import LandingView from '@/views/LandingView.vue'
import { useConnectionStore } from '@/stores/connection'
import { useSocket } from '@/composables/useSocket'

const connectionStore = useConnectionStore()
const { connected } = useSocket()
const appVersion = import.meta.env.VITE_APP_VERSION ?? ''

const statusClass = computed(() => {
  const s = connectionStore.connectionStatus
  if (s === 'Connected') return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
  if (s === 'Connecting') return 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
  return 'bg-slate-600/30 text-slate-400 border border-slate-500/40'
})

onMounted(() => {
  connectionStore.fetchState()
})
</script>
