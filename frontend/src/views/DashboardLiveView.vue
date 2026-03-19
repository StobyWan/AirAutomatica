<template>
  <div class="space-y-4">
    <!-- Drone mode: flight path, aircraft state, trends, detections, sessions -->
    <template v-if="vehicleMode === 'drone'">
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
    </template>

    <!-- Rover / Bench mode: live camera prominent, vehicle control placeholder -->
    <template v-else-if="vehicleMode === 'rover' || vehicleMode === 'bench'">
      <div
        v-if="vehicleMode === 'bench'"
        class="rounded-lg border border-amber-600/50 bg-amber-900/20 px-4 py-2 text-amber-200 text-sm font-medium"
      >
        BENCH MODE — No live actuators. Safe testing only.
      </div>
      <div class="flex gap-4 flex-wrap">
        <LiveCameraFeed class="flex-1 min-w-[320px]" />
        <VehicleControl class="flex-1 min-w-[280px]" />
      </div>
      <div class="min-w-0">
        <ConnectionHealth />
      </div>
    </template>

    <!-- Fallback when vehicle_mode not yet received -->
    <template v-else>
      <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-slate-400 text-sm">
        Loading mode…
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import FlightStatusStrip from '@/components/FlightStatusStrip.vue'
import OperationsHud from '@/components/OperationsHud.vue'
import LiveCameraFeed from '@/components/LiveCameraFeed.vue'
import LiveMap from '@/components/LiveMap.vue'
import LiveHomeControls from '@/components/LiveHomeControls.vue'
import ConnectionHealth from '@/components/ConnectionHealth.vue'
import QuickTelemetry from '@/components/QuickTelemetry.vue'
import RecentDetectionsStrip from '@/components/RecentDetectionsStrip.vue'
import LiveTabs from '@/components/LiveTabs.vue'
import VehicleControl from '@/components/VehicleControl.vue'
import { useCameraStore } from '@/stores/camera'
import { useHealthStore } from '@/stores/health'

const cameraStore = useCameraStore()
const healthStore = useHealthStore()

const vehicleMode = computed(() => {
  const mode = healthStore.lastHealth?.vehicle_mode
  return mode === 'rover' || mode === 'bench' ? mode : 'drone'
})

onMounted(() => {
  cameraStore.fetchCameraStatus()
})
</script>
