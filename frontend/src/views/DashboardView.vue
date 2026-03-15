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
      <h1 class="text-xl font-bold text-slate-100 tracking-tight">
        AIRAUTOMATICA Dashboard
        <span v-if="appVersion" class="text-slate-500 font-normal text-sm ml-2">v{{ appVersion }}</span>
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
