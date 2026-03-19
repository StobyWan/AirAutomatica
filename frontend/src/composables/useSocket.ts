import { ref } from 'vue'
import { io } from 'socket.io-client'

import { SOCKET_URL } from '@/config'

// Socket.io is served at root /socket.io. In dev, connect directly to backend when SOCKET_URL is set.
let socket: ReturnType<typeof io> | null = null
const connected = ref(false)

export function useSocket() {
  if (!socket) {
    socket = io(SOCKET_URL || undefined)
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
