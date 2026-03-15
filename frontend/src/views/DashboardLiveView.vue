<template>
  <div class="space-y-4">
    <FlightStatusStrip />
    <OperationsHud />
    <ConnectionHealth />
    <QuickTelemetry />
    <LiveTabs />
  </div>
</template>

<script setup lang="ts">
import FlightStatusStrip from '@/components/FlightStatusStrip.vue'
import OperationsHud from '@/components/OperationsHud.vue'
import ConnectionHealth from '@/components/ConnectionHealth.vue'
import QuickTelemetry from '@/components/QuickTelemetry.vue'
import LiveTabs from '@/components/LiveTabs.vue'
</script>
