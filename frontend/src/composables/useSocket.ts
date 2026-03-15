import { io } from 'socket.io-client'

const basePath = (import.meta.env.VITE_BASE_PATH || '').replace(/\/$/, '')
const path = basePath ? basePath + '/socket.io' : undefined

let socket: ReturnType<typeof io> | null = null

export function useSocket() {
  if (!socket) {
    socket = io({ path })
  }
  return socket
}
