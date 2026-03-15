<template>
  <div class="space-y-4">
    <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h2 class="text-base font-semibold text-slate-200 mb-3">Aviation</h2>
      <AviationWidget />
    </div>
    <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h2 class="text-base font-semibold text-slate-200 mb-3">Aircraft State</h2>
      <AircraftState />
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Path</h2>
        <FlightPath :width="280" :height="180" />
      </div>
      <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Trends</h2>
        <Trends />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import AviationWidget from './AviationWidget.vue'
import AircraftState from './AircraftState.vue'
import FlightPath from './FlightPath.vue'
import Trends from './Trends.vue'
</script>
