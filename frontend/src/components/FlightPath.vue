<template>
  <div class="path-svg rounded-lg overflow-hidden bg-black/20">
    <svg
      v-if="svgContent"
      :width="width"
      :height="height"
      :viewBox="`0 0 ${width} ${height}`"
      class="block"
      v-html="svgContent"
    />
    <div v-else class="flex items-center justify-center h-full text-muted text-sm">
      No path data
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTelemetryPathStore } from '@/stores/telemetryPath'
import { renderPathPlot } from '@/utils/pathPlot'

const props = withDefaults(
  defineProps<{
    width?: number
    height?: number
  }>(),
  { width: 200, height: 180 }
)

const pathStore = useTelemetryPathStore()

const svgContent = computed(() => {
  const path = pathStore.path
  const current = pathStore.currentPosition
  const detections = pathStore.detections
  return renderPathPlot(path, current, detections, null, {
    width: props.width,
    height: props.height,
  })
})
</script>

<style scoped>
.path-svg {
  width: 100%;
  height: 180px;
}
</style>
