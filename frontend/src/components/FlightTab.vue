<template>
  <div class="space-y-6">
    <section class="rounded-xl border border-slate-600/80 bg-slate-800/60 p-4">
      <h2 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-4">Aviation</h2>
      <AviationWidget />
    </section>
    <section class="rounded-xl border border-slate-600/80 bg-slate-800/60 p-4">
      <h2 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-4">Aircraft State</h2>
      <AircraftState />
    </section>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <section class="rounded-xl border border-slate-600/80 bg-slate-800/60 p-4">
        <h2 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">Path</h2>
        <PathMap class="h-[200px] w-full" />
      </section>
      <section class="rounded-xl border border-slate-600/80 bg-slate-800/60 p-4">
        <h2 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">Trends</h2>
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
