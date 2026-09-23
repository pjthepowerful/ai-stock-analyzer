import { useEffect, useRef } from 'react'

const WS_URL = 'ws://127.0.0.1:4141/ws'

export interface WsEvent {
  event: string
  data: Record<string, unknown>
}

export function useWebSocket(onEvent: (e: WsEvent) => void) {
  const handlerRef = useRef(onEvent)
  handlerRef.current = onEvent

  useEffect(() => {
    let ws: WebSocket | null = null
    let closed = false
    let pingTimer: ReturnType<typeof setInterval> | null = null

    function connect() {
      if (closed) return
      ws = new WebSocket(WS_URL)
      ws.onopen = () => {
        pingTimer = setInterval(() => {
          if (ws?.readyState === 1) ws.send(JSON.stringify({ type: 'ping' }))
        }, 25_000)
      }
      ws.onmessage = (msg) => {
        try {
          const parsed = JSON.parse(msg.data)
          if (parsed.event === 'pong') return
          handlerRef.current(parsed)
        } catch {
          /* ignore malformed frames */
        }
      }
      ws.onclose = () => {
        if (pingTimer) clearInterval(pingTimer)
        if (!closed) setTimeout(connect, 3000)
      }
    }
    connect()

    return () => {
      closed = true
      if (pingTimer) clearInterval(pingTimer)
      ws?.close()
    }
  }, [])
}
