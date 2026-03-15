<template>
  <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <h2 class="text-base font-semibold text-slate-200 mb-3">Replay</h2>

    <div v-if="loading" class="py-12 flex items-center justify-center gap-2 text-slate-400">
      <BaseSpinner color="slate" />
      <span>Loading replay data…</span>
    </div>

    <div v-else-if="storeError" class="py-8 text-center text-red-300 text-sm">
      {{ storeError }}
    </div>

    <div v-else-if="!hasData" class="py-12 text-center text-slate-500 text-sm">
      No telemetry data for this session. Replay requires recorded telemetry.
    </div>

    <div v-else class="space-y-4">
      <!-- Top: Video | Map -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="aspect-video rounded-lg overflow-hidden bg-black/40">
          <ReplayVideo v-if="hasRecording" />
          <div
            v-else
            class="w-full h-full flex items-center justify-center text-slate-500 text-sm"
          >
            No recording for this session
          </div>
        </div>
        <div class="aspect-video rounded-lg overflow-hidden bg-slate-900/50">
          <ReplayMap />
        </div>
      </div>

      <!-- Charts -->
      <div class="rounded-lg overflow-hidden bg-slate-900/30">
        <ReplayCharts />
      </div>

      <!-- Timeline controls -->
      <ReplayTimeline />
    </div>
  </section>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { watch, onMounted } from 'vue'
import { useReplayStore } from '@/stores/replay'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import ReplayVideo from './ReplayVideo.vue'
import ReplayMap from './ReplayMap.vue'
import ReplayCharts from './ReplayCharts.vue'
import ReplayTimeline from './ReplayTimeline.vue'

const props = defineProps<{
  sessionId: number
}>()

const store = useReplayStore()
const { loading, error: storeError, hasData, hasRecording } =
  storeToRefs(store)

function maybeLoad() {
  if (Number.isFinite(props.sessionId)) {
    store.load(props.sessionId)
  }
}

watch(
  () => props.sessionId,
  (sid) => {
    if (Number.isFinite(sid)) store.load(sid)
  }
)

onMounted(maybeLoad)
</script>
