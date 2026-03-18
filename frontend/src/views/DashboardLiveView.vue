<template>
  <div class="space-y-4">
    <FlightStatusStrip />
    <div class="flex gap-4 flex-wrap">
      <OperationsHud class="flex-1 min-w-[280px]" />
      <LiveCameraFeed class="flex-1 min-w-[280px]" />
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-[30%_1fr] lg:grid-cols-1 gap-4">
      <div class="min-w-0">
        <ConnectionHealth />
      </div>
      <div class="min-h-[420px] min-w-0 overflow-hidden">
        <div class="aspect-video sm:aspect-auto sm:h-full rounded-lg overflow-hidden bg-slate-900/50 w-full min-h-[420px]">
          <LiveMap />
        </div>
      </div>
    </div>
    <div class="space-y-4">
      <LiveHomeControls />
      <QuickTelemetry />
      <RecentDetectionsStrip />
    </div>
    <LiveTabs />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import FlightStatusStrip from '@/components/FlightStatusStrip.vue'
import OperationsHud from '@/components/OperationsHud.vue'
import LiveCameraFeed from '@/components/LiveCameraFeed.vue'
import LiveMap from '@/components/LiveMap.vue'
import LiveHomeControls from '@/components/LiveHomeControls.vue'
import ConnectionHealth from '@/components/ConnectionHealth.vue'
import QuickTelemetry from '@/components/QuickTelemetry.vue'
import RecentDetectionsStrip from '@/components/RecentDetectionsStrip.vue'
import LiveTabs from '@/components/LiveTabs.vue'
import { useCameraStore } from '@/stores/camera'

const cameraStore = useCameraStore()

onMounted(() => {
  cameraStore.fetchCameraStatus()
})
</script>
