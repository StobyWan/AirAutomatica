<template>
  <div class="space-y-6">
    <section class="rounded-xl border border-slate-700 bg-slate-800/50 p-4">
      <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Aviation</h2>
      <AviationWidget />
    </section>
    <section class="rounded-xl border border-slate-700 bg-slate-800/50 p-4">
      <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Aircraft State</h2>
      <AircraftState />
    </section>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <section class="rounded-xl border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Path</h2>
        <PathMap class="h-[200px] w-full" />
      </section>
      <section class="rounded-xl border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Trends</h2>
        <Trends />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import AviationWidget from './AviationWidget.vue'
import AircraftState from './AircraftState.vue'
import PathMap from './PathMap.vue'
import Trends from './Trends.vue'
</script>
