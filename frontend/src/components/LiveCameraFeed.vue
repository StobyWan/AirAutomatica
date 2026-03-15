<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <h2 class="text-base font-semibold text-slate-200 mb-3">Live Camera</h2>

    <div
      v-if="cameraRecording"
      class="aspect-video rounded bg-slate-900/50 flex items-center justify-center"
    >
      <p class="text-slate-500 text-sm">Camera recording — preview unavailable</p>
    </div>

    <div
      v-else-if="!cameraAvailable"
      class="aspect-video rounded bg-slate-900/50 flex items-center justify-center"
    >
      <p class="text-slate-500 text-sm">Camera not available</p>
    </div>

    <div
      v-else-if="!cameraReady"
      class="aspect-video rounded bg-slate-900/50 flex items-center justify-center"
    >
      <p class="text-slate-500 text-sm">Turn on Camera Ready in Operations to view live feed</p>
    </div>

    <div v-else class="relative aspect-video rounded bg-black overflow-hidden">
      <img
        :src="previewUrl"
        class="w-full h-full object-contain"
        alt="Live camera preview"
        @error="onPreviewError"
      />
      <p
        v-if="previewError"
        class="absolute inset-0 flex items-center justify-center bg-slate-900/80 text-slate-400 text-sm"
      >
        {{ previewError }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useHealthStore } from '@/stores/health'
import { API_BASE } from '@/config'

const healthStore = useHealthStore()

const cameraRecording = computed(
  () => healthStore.lastHealth?.camera_recording === true
)

const cameraAvailable = computed(
  () => healthStore.lastHealth?.camera_recording_available !== false
)

const cameraReady = computed(
  () => healthStore.lastHealth?.camera_ready === true
)

const previewUrl = computed(() => {
  const base = String(API_BASE ?? '').replace(/\/$/, '')
  return base ? `${base}/camera/preview/stream` : '/camera/preview/stream'
})

const previewError = ref<string | null>(null)

function onPreviewError() {
  previewError.value = 'Unable to load preview'
}
</script>
