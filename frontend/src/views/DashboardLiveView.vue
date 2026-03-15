<template>
  <div class="space-y-4">
    <FlightStatusStrip />
    <div class="flex gap-4 flex-wrap">
      <OperationsHud class="flex-1 min-w-[280px]" />
      <LiveCameraFeed class="flex-1 min-w-[280px]" />
    </div>
    <div class="aspect-video rounded-lg overflow-hidden bg-slate-900/50">
      <LiveMap />
    </div>
    <ConnectionHealth />
    <QuickTelemetry />
    <RecentDetectionsStrip />
    <LiveTabs />
  </div>
</template>

<script setup lang="ts">
import FlightStatusStrip from '@/components/FlightStatusStrip.vue'
import OperationsHud from '@/components/OperationsHud.vue'
import LiveCameraFeed from '@/components/LiveCameraFeed.vue'
import LiveMap from '@/components/LiveMap.vue'
import ConnectionHealth from '@/components/ConnectionHealth.vue'
import QuickTelemetry from '@/components/QuickTelemetry.vue'
import RecentDetectionsStrip from '@/components/RecentDetectionsStrip.vue'
import LiveTabs from '@/components/LiveTabs.vue'
</script>
