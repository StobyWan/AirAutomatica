import { defineStore } from 'pinia'
import { ref, shallowRef, computed } from 'vue'
import {
  getConnectionState,
  getAvailablePorts,
  detectConnection,
  setConnectionMode,
  disconnect,
  normalizeConnectionState,
  type ConnectionMode,
} from '@/api/connection'
import type { ConnectionStateResponse, PortInfo } from '@/types'
import { useSocket } from '@/composables/useSocket'
import { useHealthStore } from '@/stores/health'
import { ApiError } from '@/api/client'

const LAST_PORT_KEY = 'airautomatica_last_port'

function loadLastPort(): { port: string; baud: number } | null {
  try {
    const raw = localStorage.getItem(LAST_PORT_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as { port?: string; baud?: number }
    if (typeof data?.port === 'string' && data.port && typeof data?.baud === 'number') {
      return { port: data.port, baud: data.baud }
    }
    return null
  } catch {
    return null
  }
}

function saveLastPort(port: string, baud: number): void {
  localStorage.setItem(LAST_PORT_KEY, JSON.stringify({ port, baud }))
}

function clearLastPort(): void {
  localStorage.removeItem(LAST_PORT_KEY)
}

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

  const lastPort = loadLastPort()
  const lastConnectedPort = ref<string | null>(lastPort?.port ?? null)
  const lastConnectedBaud = ref<number | null>(lastPort?.baud ?? null)
  const connectingToLast = ref(false)

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

  async function detect(opts?: { port?: string; baud?: number }) {
    loading.value = true
    error.value = null
    try {
      const res = await detectConnection(opts)
      await fetchState()
      if (res.detected && res.port && res.baud != null) {
        lastConnectedPort.value = res.port
        lastConnectedBaud.value = res.baud
        saveLastPort(res.port, res.baud)
      }
      return res
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      error.value = msg
      throw e
    } finally {
      loading.value = false
    }
  }

  async function connectToLastPort() {
    const port = lastConnectedPort.value
    const baud = lastConnectedBaud.value
    if (!port || baud == null) return
    connectingToLast.value = true
    try {
      return await detect({ port, baud })
    } finally {
      connectingToLast.value = false
    }
  }

  async function setMode(m: ConnectionMode, port?: string, baud?: number) {
    loading.value = true
    error.value = null
    try {
      await setConnectionMode(m, port, baud)
      await fetchState()
      if ((m === 'ardupilot' || m === 'inav') && port && baud != null) {
        lastConnectedPort.value = port
        lastConnectedBaud.value = baud
        saveLastPort(port, baud)
      }
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
      lastConnectedPort.value = null
      lastConnectedBaud.value = null
      clearLastPort()
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
    lastConnectedPort,
    lastConnectedBaud,
    connectingToLast,
    fetchState,
    fetchPorts,
    updatePortsFromSocket,
    detect,
    setMode,
    connectToLastPort,
    disconnect: doDisconnect,
    clearError,
  }
})
