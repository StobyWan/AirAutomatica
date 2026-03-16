<template>
  <div class="relative w-full min-h-[160px] rounded-[10px] overflow-hidden bg-slate-900/50">
    <div ref="mapContainerRef" class="absolute inset-0 w-full h-full rounded-[10px]" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useTelemetryPathStore } from '@/stores/telemetryPath'
import { useStateStore } from '@/stores/state'
import type { PathPoint } from '@/api/session'

const props = withDefaults(
  defineProps<{
    path?: PathPoint[]
    homeLat?: number | null
    homeLon?: number | null
    detections?: PathPoint[]
    showPositionMarker?: boolean
  }>(),
  {
    path: undefined,
    homeLat: undefined,
    homeLon: undefined,
    detections: undefined,
    showPositionMarker: true,
  }
)

const pathStore = useTelemetryPathStore()
const stateStore = useStateStore()
const { path: storePath, currentPosition, detections: storeDetections } = storeToRefs(pathStore)
const { lastState } = storeToRefs(stateStore)

const useSessionData = computed(() => props.path !== undefined)

const path = computed(() =>
  useSessionData.value ? (props.path ?? []) : storePath.value
)
const homeLat = computed(() =>
  useSessionData.value ? (props.homeLat ?? null) : (lastState.value?.home_lat ?? null)
)
const homeLon = computed(() =>
  useSessionData.value ? (props.homeLon ?? null) : (lastState.value?.home_lon ?? null)
)
const detections = computed(() =>
  useSessionData.value ? (props.detections ?? []) : storeDetections.value
)

const mapContainerRef = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let polyline: L.Polyline | null = null
let marker: L.Marker | null = null
let homeMarker: L.Marker | null = null
let detectionLayer: L.LayerGroup | null = null

const defaultCenter: [number, number] = [37.5, -122.3]

function initMap() {
  const el = mapContainerRef.value
  if (!el || map) return

  map = L.map(el, {
    attributionControl: false,
    zoomControl: false,
  }).setView(defaultCenter, 14)
  L.control.zoom({ position: 'topleft' }).addTo(map)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
  }).addTo(map)

  const positionPinHtml = (color: string) =>
    `<div style="position:relative;width:24px;height:32px;margin-left:-12px;margin-top:-32px">
      <svg width="24" height="32" viewBox="0 0 24 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20C24 5.4 18.6 0 12 0z" fill="${color}" stroke="#0f172a" stroke-width="2"/>
        <circle cx="12" cy="12" r="4" fill="#0f172a"/>
      </svg>
    </div>`

  polyline = L.polyline([], { color: '#3b82f6', weight: 3 }).addTo(map)
  marker = L.marker(defaultCenter, {
    icon: L.divIcon({
      className: 'path-position-marker',
      html: positionPinHtml('#22d3ee'),
      iconSize: [24, 32],
      iconAnchor: [12, 32],
    }),
  }).addTo(map)

  detectionLayer = L.layerGroup().addTo(map)

  if (homeLat.value != null && homeLon.value != null) {
    homeMarker = L.marker([homeLat.value, homeLon.value], {
      icon: L.divIcon({
        className: 'path-home-marker',
        html: positionPinHtml('#f59e0b'),
        iconSize: [24, 32],
        iconAnchor: [12, 32],
      }),
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
  if (!props.showPositionMarker) {
    marker.setOpacity(0)
    return
  }
  const pos = currentPosition.value
  if (pos?.lat != null && pos?.lon != null) {
    marker.setLatLng([pos.lat, pos.lon])
    marker.setOpacity(1)
  } else {
    marker.setOpacity(0)
  }
}

const homePinHtml =
  '<div style="position:relative;width:24px;height:32px;margin-left:-12px;margin-top:-32px"><svg width="24" height="32" viewBox="0 0 24 32" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20C24 5.4 18.6 0 12 0z" fill="#f59e0b" stroke="#0f172a" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="#0f172a"/></svg></div>'

function updateHomeMarker() {
  if (!map) return
  if (homeMarker) {
    map.removeLayer(homeMarker)
    homeMarker = null
  }
  if (homeLat.value != null && homeLon.value != null) {
    homeMarker = L.marker([homeLat.value, homeLon.value], {
      icon: L.divIcon({
        className: 'path-home-marker',
        html: homePinHtml,
        iconSize: [24, 32],
        iconAnchor: [12, 32],
      }),
    }).addTo(map)
  }
}

const detectionPinHtml =
  '<div style="position:relative;width:20px;height:26px;margin-left:-10px;margin-top:-26px"><svg width="20" height="26" viewBox="0 0 20 26" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 0C4.5 0 0 4.5 0 10c0 7.5 10 16 10 16s10-8.5 10-16C20 4.5 15.5 0 10 0z" fill="#ef4444" stroke="#0f172a" stroke-width="1.5"/><circle cx="10" cy="10" r="3" fill="#0f172a"/></svg></div>'

function updateDetectionMarkers() {
  if (!map || !detectionLayer) return
  detectionLayer.clearLayers()
  const pts = detections.value.filter((p) => p.lat != null && p.lon != null)
  for (const p of pts) {
    L.marker([p.lat!, p.lon!], {
      icon: L.divIcon({
        className: 'path-detection-marker',
        html: detectionPinHtml,
        iconSize: [20, 26],
        iconAnchor: [10, 26],
      }),
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

<style>
.leaflet-marker-icon.path-position-marker,
.leaflet-marker-icon.path-home-marker,
.leaflet-marker-icon.path-detection-marker {
  background: none !important;
  border: none !important;
}
</style>
