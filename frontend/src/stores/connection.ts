import { defineStore } from 'pinia'
import { ref, shallowRef, computed } from 'vue'
import {
  getConnectionState,
  getAvailablePorts,
  detectConnection,
  setConnectionMode,
  disconnect,
  normalizeConnectionState,
} from '@/api/connection'
import type { ConnectionStateResponse, PortInfo } from '@/types'
import { useSocket } from '@/composables/useSocket'
import { useHealthStore } from '@/stores/health'
import { ApiError } from '@/api/client'

export type ConnectionStatus =
  | 'Connecting'
  | 'Connected'
  | 'Disconnected'
  | 'Setup'

export const useConnectionStore = defineStore('connection', () => {
  const connectionState = ref<string>('setup')
  const sessionState = ref<string>('none')
  const mode = ref<string | null>(null)
  const sessionId = ref<number | null>(null)
  const detectionResult = shallowRef<ConnectionStateResponse['detection_result']>(
    null
  )
  const connectionStatus = ref<ConnectionStatus>('Disconnected')
  const loading = ref(false)
  const error = ref<string | null>(null)
  const ports = ref<PortInfo[]>([])
  const portsLoading = ref(false)
  const portsError = ref<string | null>(null)

  const { socket } = useSocket()

  socket.on('connect', () => {
    connectionStatus.value = 'Connected'
    fetchState()
  })
  socket.on('disconnect', () => {
    connectionStatus.value = 'Disconnected'
  })
  socket.on('connect_error', () => {
    connectionStatus.value = 'Disconnected'
  })

  const healthStore = useHealthStore()
  const liveSessionId = computed(() => {
    if (sessionId.value != null) return sessionId.value
    return healthStore.lastHealth?.session_id ?? null
  })

  async function fetchState() {
    loading.value = true
    error.value = null
    try {
      const res = await getConnectionState()
      const norm = normalizeConnectionState(res)
      connectionState.value = norm.connection_state
      sessionState.value = norm.session_state ?? 'none'
      mode.value = norm.mode
      sessionId.value = norm.session_id
      detectionResult.value = norm.detection_result
      return norm
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      error.value = msg
      throw e
    } finally {
      loading.value = false
    }
  }

  async function detect() {
    loading.value = true
    error.value = null
    try {
      const res = await detectConnection()
      await fetchState()
      return res
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      error.value = msg
      throw e
    } finally {
      loading.value = false
    }
  }

  async function setMode(m: 'mock' | 'ardupilot' | 'inav') {
    loading.value = true
    error.value = null
    try {
      await setConnectionMode(m)
      await fetchState()
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      error.value = msg
      throw e
    } finally {
      loading.value = false
    }
  }

  async function doDisconnect() {
    loading.value = true
    error.value = null
    try {
      await disconnect()
      await fetchState()
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      error.value = msg
      throw e
    } finally {
      loading.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  async function fetchPorts() {
    portsLoading.value = true
    portsError.value = null
    try {
      const res = await getAvailablePorts()
      ports.value = res.ports ?? []
      if (res.error) {
        portsError.value = res.error
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      portsError.value = msg
      ports.value = []
    } finally {
      portsLoading.value = false
    }
  }

  function updatePortsFromSocket(payload: { ports: PortInfo[] }) {
    if (payload?.ports && Array.isArray(payload.ports)) {
      ports.value = payload.ports
      portsError.value = null
    }
  }

  return {
    connectionState,
    sessionState,
    mode,
    sessionId,
    liveSessionId,
    detectionResult,
    connectionStatus,
    loading,
    error,
    ports,
    portsLoading,
    portsError,
    fetchState,
    fetchPorts,
    updatePortsFromSocket,
    detect,
    setMode,
    disconnect: doDisconnect,
    clearError,
  }
})
