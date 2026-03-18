import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getCameraStatus } from '@/api/camera'
import type { CameraStatusResponse } from '@/api/camera'

export const useCameraStore = defineStore('camera', () => {
  const cameraStatus = ref<CameraStatusResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchCameraStatus() {
    loading.value = true
    error.value = null
    try {
      cameraStatus.value = await getCameraStatus()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load camera status'
      cameraStatus.value = null
    } finally {
      loading.value = false
    }
  }

  return { cameraStatus, loading, error, fetchCameraStatus }
})
