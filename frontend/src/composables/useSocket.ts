import { ref } from 'vue'
import { io } from 'socket.io-client'

const basePath = (import.meta.env.VITE_BASE_PATH || '').replace(/\/$/, '')
const path = basePath ? basePath + '/socket.io' : undefined

let socket: ReturnType<typeof io> | null = null
const connected = ref(false)

export function useSocket() {
  if (!socket) {
    socket = io({ path })
    connected.value = socket.connected
    socket.on('connect', () => {
      connected.value = true
    })
    socket.on('disconnect', () => {
      connected.value = false
    })
    socket.on('connect_error', () => {
      connected.value = false
    })
  }
  return { socket, connected }
}
