<template>
  <div class="relative" style="height: 200px">
    <canvas ref="chartCanvasRef" />
    <div
      v-if="scrubberXPct != null"
      class="absolute top-0 bottom-0 w-0.5 bg-cyan-400 pointer-events-none z-10"
      :style="{ left: scrubberXPct * 100 + '%' }"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { Chart, registerables, type ChartConfiguration } from 'chart.js'
import { useReplayStore } from '@/stores/replay'

Chart.register(...registerables)

const store = useReplayStore()
const { chartData, currentOffsetPct, tStartMs } = storeToRefs(store)

const chartCanvasRef = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

const scrubberXPct = computed(() => currentOffsetPct.value)

function buildChartConfig(): ChartConfiguration<'line', { x: number; y: number }[], number> | null {
  const data = chartData.value
  if (!data || data.labels.length === 0) return null

  const points = data.labels.map((x, i) => ({ x, y: data.speedKmh[i] ?? 0 }))
  const bearingPoints = data.labels.map((x, i) => ({ x, y: data.bearingDeg[i] ?? 0 }))
  const rollPoints = data.labels.map((x, i) => ({ x, y: data.rollDeg[i] ?? 0 }))

  return {
    type: 'line',
    data: {
      datasets: [
        {
          label: 'Speed (km/h)',
          data: points,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          tension: 0.2,
          fill: false,
          yAxisID: 'y',
        },
        {
          label: 'Bearing (°)',
          data: bearingPoints,
          borderColor: '#ec4899',
          backgroundColor: 'rgba(236, 72, 153, 0.1)',
          tension: 0.2,
          fill: false,
          yAxisID: 'y1',
        },
        {
          label: 'Roll (°)',
          data: rollPoints,
          borderColor: '#f97316',
          backgroundColor: 'rgba(249, 115, 22, 0.1)',
          tension: 0.2,
          fill: false,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, position: 'top' },
        tooltip: { enabled: true },
      },
      scales: {
        x: {
          type: 'linear',
          title: { display: true, text: 'Time (s)' },
          min: data.labels[0],
          max: data.labels[data.labels.length - 1],
        },
        y: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Speed (km/h)' },
          min: 0,
        },
        y1: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: '°' },
          grid: { drawOnChartArea: false },
        },
      },
      onClick: (ev) => {
        const canvas = chartCanvasRef.value
        if (!canvas || !chart) return
        const native = ev.native as MouseEvent | null
        if (!native) return
        const rect = canvas.getBoundingClientRect()
        const x = native.clientX - rect.left
        const xScale = chart.scales.x
        const xVal = xScale.getValueForPixel(x)
        if (xVal != null && !Number.isNaN(xVal)) {
          const tsMs = tStartMs.value + xVal * 1000
          store.seekToTimestamp(tsMs)
        }
      },
    },
  }
}

function initChart() {
  const canvas = chartCanvasRef.value
  if (!canvas) return

  const config = buildChartConfig()
  if (!config) return

  chart = new Chart(canvas, config)
}

onMounted(() => {
  initChart()
})

watch(chartData, () => {
  if (chart) {
    chart.destroy()
    chart = null
  }
  initChart()
})

onUnmounted(() => {
  if (chart) {
    chart.destroy()
    chart = null
  }
})
</script>
