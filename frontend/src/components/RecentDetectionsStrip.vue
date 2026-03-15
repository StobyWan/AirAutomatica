<template>
  <div
    v-if="detectionsStore.detections.length > 0"
    class="rounded-lg border border-cyan-500/30 bg-slate-800/40 px-3 py-2"
  >
    <button
      type="button"
      class="flex w-full items-center justify-between gap-2 text-left"
      @click="collapsed = !collapsed"
    >
      <span class="text-xs font-medium text-slate-300">
        Recent Detections
        <span class="ml-1.5 text-cyan-400">{{ detectionsStore.detections.length }}</span>
      </span>
      <svg
        class="h-4 w-4 shrink-0 text-slate-500 transition-transform"
        :class="{ 'rotate-180': !collapsed }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>
    <div
      v-show="!collapsed"
      class="mt-2 flex gap-2 overflow-x-auto pb-1"
    >
      <div
        v-for="(d, i) in displayDetections"
        :key="i"
        class="shrink-0 rounded-md border border-slate-600/60 bg-slate-800/60 px-2.5 py-1.5 text-xs"
      >
        <span class="font-medium text-slate-200">{{ d.label }}</span>
        <span class="ml-1.5 text-slate-400">{{ formatConf(d.confidence) }}</span>
        <span
          v-if="d.source_backend"
          class="ml-1 text-slate-500"
        >
          · {{ fmtSourceBackend(d.source_backend).text }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDetectionsStore } from '@/stores/detections'
import { fmtSourceBackend } from '@/utils/formatters'

const detectionsStore = useDetectionsStore()
const collapsed = ref(false)

onMounted(() => {
  detectionsStore.fetchRecentDetections()
})

const displayDetections = computed(() =>
  detectionsStore.detections.slice(0, 8)
)

function formatConf(c: number): string {
  return c != null ? (c * 100).toFixed(0) + '%' : '—'
}
</script>
