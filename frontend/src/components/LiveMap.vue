<template>
  <div ref="mapContainerRef" class="w-full h-full min-h-[200px]" />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useTelemetryPathStore } from '@/stores/telemetryPath'
import { useStateStore } from '@/stores/state'

const pathStore = useTelemetryPathStore()
const stateStore = useStateStore()
const { path, currentPosition, detections } = storeToRefs(pathStore)
const { lastState } = storeToRefs(stateStore)

const homeLat = computed(() => lastState.value?.home_lat ?? null)
const homeLon = computed(() => lastState.value?.home_lon ?? null)

const mapContainerRef = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let polyline: L.Polyline | null = null
let marker: L.Marker | null = null
let homeMarker: L.CircleMarker | null = null
let detectionLayer: L.LayerGroup | null = null

const defaultCenter: [number, number] = [37.5, -122.3]

function initMap() {
  const el = mapContainerRef.value
  if (!el || map) return

  map = L.map(el, { attributionControl: false }).setView(defaultCenter, 14)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
  }).addTo(map)

  polyline = L.polyline([], { color: '#3b82f6', weight: 3 }).addTo(map)
  marker = L.marker(defaultCenter, {
    icon: L.divIcon({
      className: 'live-position-marker',
      html: '<div style="width:16px;height:16px;background:#22d3ee;border:2px solid #0f172a;border-radius:50%;transform:translate(-50%,-50%)"></div>',
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    }),
  }).addTo(map)

  detectionLayer = L.layerGroup().addTo(map)

  if (homeLat.value != null && homeLon.value != null) {
    homeMarker = L.circleMarker([homeLat.value, homeLon.value], {
      radius: 6,
      color: '#f59e0b',
      fillColor: '#f59e0b',
      fillOpacity: 1,
      weight: 1,
    }).addTo(map)
  }
}

function updatePath() {
  if (!map || !polyline) return
  const pts = path.value.filter((p) => p.lat != null && p.lon != null)
  const latlngs = pts.map((p) => [p.lat!, p.lon!] as [number, number])
  polyline.setLatLngs(latlngs)
  if (latlngs.length > 0) {
    const bounds = L.latLngBounds(latlngs)
    map.fitBounds(bounds.pad(0.1))
  }
}

function updateMarker() {
  if (!marker) return
  const pos = currentPosition.value
  if (pos?.lat != null && pos?.lon != null) {
    marker.setLatLng([pos.lat, pos.lon])
    marker.setOpacity(1)
  } else {
    marker.setOpacity(0)
  }
}

function updateHomeMarker() {
  if (!map) return
  if (homeMarker) {
    map.removeLayer(homeMarker)
    homeMarker = null
  }
  if (homeLat.value != null && homeLon.value != null) {
    homeMarker = L.circleMarker([homeLat.value, homeLon.value], {
      radius: 6,
      color: '#f59e0b',
      fillColor: '#f59e0b',
      fillOpacity: 1,
      weight: 1,
    }).addTo(map)
  }
}

function updateDetectionMarkers() {
  if (!map || !detectionLayer) return
  detectionLayer.clearLayers()
  const pts = detections.value.filter((p) => p.lat != null && p.lon != null)
  for (const p of pts) {
    L.circleMarker([p.lat!, p.lon!], {
      radius: 4,
      color: '#ef4444',
      fillColor: '#ef4444',
      fillOpacity: 0.8,
      weight: 1,
    }).addTo(detectionLayer)
  }
}

onMounted(() => {
  initMap()
  updatePath()
  updateMarker()
  updateHomeMarker()
  updateDetectionMarkers()
})

watch(path, updatePath)
watch(currentPosition, updateMarker)
watch([homeLat, homeLon], updateHomeMarker)
watch(detections, updateDetectionMarkers)

onUnmounted(() => {
  if (map) {
    map.remove()
    map = null
  }
  polyline = null
  marker = null
  homeMarker = null
  detectionLayer = null
})
</script>
