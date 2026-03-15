<template>
  <video
    ref="videoRef"
    class="w-full h-full object-contain"
    preload="metadata"
    :src="videoSrc"
    playsinline
    controls
    @play="onVideoPlay"
    @pause="onVideoPause"
    @seeked="onVideoSeeked"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useReplayStore } from '@/stores/replay'
import { recordingsUrl } from '@/config'

const store = useReplayStore()
const { currentSample, primaryRecording, recordingOffsetSec, isPlaying, playbackSpeed } =
  storeToRefs(store)

const DRIFT_RESYNC_THRESHOLD_SEC = 0.5
const SEEK_DEBOUNCE_MS = 150

const videoRef = ref<HTMLVideoElement | null>(null)
let programmaticSeekUntil = 0

const videoSrc = computed(() => {
  const rec = primaryRecording.value
  return rec ? recordingsUrl(rec.filename) : ''
})

function syncVideoToStore() {
  const video = videoRef.value
  const rec = primaryRecording.value
  const sample = currentSample.value
  if (!video || !rec || !sample) return

  const recStart = new Date(rec.timestamp).getTime()
  const sampleTs = new Date(sample.timestamp).getTime()
  const offsetSec = (sampleTs - recStart) / 1000 + (recordingOffsetSec.value ?? 0)
  const targetTime = Math.max(0, offsetSec)

  const dur = rec.duration_sec ?? video.duration
  if (dur != null && targetTime > dur) return

  if (video.readyState >= 1) {
    if (isPlaying.value) {
      const drift = Math.abs(video.currentTime - targetTime)
      if (drift < DRIFT_RESYNC_THRESHOLD_SEC) return
    } else {
      const nearMatch = Math.abs(video.currentTime - targetTime) < 0.05
      if (nearMatch) return
    }
    programmaticSeekUntil = Date.now() + SEEK_DEBOUNCE_MS
    video.currentTime = targetTime
  } else {
    video.addEventListener(
      'loadedmetadata',
      () => {
        programmaticSeekUntil = Date.now() + SEEK_DEBOUNCE_MS
        video.currentTime = targetTime
      },
      { once: true }
    )
  }
}

watch(
  [currentSample, primaryRecording],
  () => syncVideoToStore(),
  { immediate: true }
)

watch(isPlaying, (playing) => {
  const video = videoRef.value
  if (!video) return
  if (playing) video.play().catch(() => {})
  else video.pause()
})

watch(playbackSpeed, (speed) => {
  const video = videoRef.value
  if (video) video.playbackRate = speed
})

function onVideoPlay() {
  store.play()
}

function onVideoPause() {
  store.pause()
}

function onVideoSeeked() {
  if (Date.now() < programmaticSeekUntil) return
  const video = videoRef.value
  const rec = primaryRecording.value
  if (!video || !rec) return

  const recStart = new Date(rec.timestamp).getTime()
  const offsetSec = video.currentTime - (recordingOffsetSec.value ?? 0)
  const tsMs = recStart + offsetSec * 1000
  store.seekToTimestamp(tsMs)
}

onUnmounted(() => {
  store.pause()
})
</script>
