import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'

export type WSStatus = 'connecting' | 'open' | 'closed'

export interface UseWebSocketOptions {
  onMessage: (data: any) => void
  onStatusChange?: (status: WSStatus) => void
}

export function useWebSocket(path: string, options: UseWebSocketOptions) {
  const status = ref<WSStatus>('closed')
  let ws: WebSocket | null = null
  let reconnectAttempt = 0
  let reconnectTimer: number | null = null
  let disposed = false
  const maxDelay = 30000

  function getUrl() {
    const auth = useAuthStore()
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${location.host}${path}?token=${auth.token}`
  }

  function connect() {
    if (disposed) return
    const auth = useAuthStore()
    if (!auth.token) {
      status.value = 'closed'
      return
    }

    try {
      ws = new WebSocket(getUrl())
      ws.binaryType = 'arraybuffer'
    } catch {
      scheduleReconnect()
      return
    }

    status.value = 'connecting'
    options.onStatusChange?.('connecting')

    ws.onopen = () => {
      status.value = 'open'
      reconnectAttempt = 0
      options.onStatusChange?.('open')
    }

    ws.onmessage = (event) => {
      try {
        const text = typeof event.data === 'string'
          ? event.data
          : new TextDecoder().decode(event.data as ArrayBuffer)
        const data = JSON.parse(text)
        options.onMessage(data)
      } catch {}
    }

    ws.onclose = (event) => {
      status.value = 'closed'
      options.onStatusChange?.('closed')
      ws = null
      if (!disposed && event.code !== 4001) {
        scheduleReconnect()
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function scheduleReconnect() {
    if (disposed) return
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), maxDelay)
    const jitter = delay * (0.5 + Math.random() * 0.5)
    reconnectAttempt++
    reconnectTimer = window.setTimeout(connect, jitter)
  }

  function close() {
    disposed = true
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
    ws = null
  }

  connect()

  onUnmounted(close)

  return { status, close, reconnect: connect }
}
