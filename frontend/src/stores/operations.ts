import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as sessionApi from '@/api/session'
import * as cameraApi from '@/api/camera'
import { useConnectionStore } from '@/stores/connection'
import { useHealthStore } from '@/stores/health'

export const useOperationsStore = defineStore('operations', () => {
  const connectionStore = useConnectionStore()
  const healthStore = useHealthStore()

  const startingSession = ref(false)
  const stoppingSession = ref(false)
  const stoppingRecording = ref(false)
  const startingRecording = ref(false)
  const opsError = ref('')

  async function startSession() {
    startingSession.value = true
    opsError.value = ''
    try {
      await sessionApi.startSession()
      await connectionStore.fetchState()
    } catch (e) {
      opsError.value = e instanceof Error ? e.message : 'Failed to start session'
      throw e
    } finally {
      startingSession.value = false
    }
  }

  async function stopSession() {
    stoppingSession.value = true
    opsError.value = ''
    try {
      await sessionApi.stopSession()
      await connectionStore.fetchState()
    } catch (e) {
      opsError.value = e instanceof Error ? e.message : 'Failed to stop session'
      throw e
    } finally {
      stoppingSession.value = false
    }
  }

  async function startRecording() {
    startingRecording.value = true
    opsError.value = ''
    try {
      await cameraApi.startRecording()
    } catch (e) {
      opsError.value = e instanceof Error ? e.message : 'Failed to start recording'
      throw e
    } finally {
      startingRecording.value = false
    }
  }

  async function stopRecording() {
    stoppingRecording.value = true
    opsError.value = ''
    try {
      await cameraApi.stopRecording()
    } catch (e) {
      opsError.value = e instanceof Error ? e.message : 'Failed to stop recording'
      throw e
    } finally {
      stoppingRecording.value = false
    }
  }

  async function setCameraReady(next: boolean) {
    opsError.value = ''
    try {
      await cameraApi.postCameraReady(next)
      healthStore.patchHealth({ camera_ready: next })
    } catch (e) {
      opsError.value = e instanceof Error ? e.message : 'Failed to set camera ready'
      throw e
    }
  }

  function clearOpsError() {
    opsError.value = ''
  }

  return {
    startingSession,
    stoppingSession,
    stoppingRecording,
    startingRecording,
    opsError,
    startSession,
    stopSession,
    startRecording,
    stopRecording,
    setCameraReady,
    clearOpsError,
  }
})
