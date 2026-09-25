import { useEffect, useRef } from 'react'
import { API_BASE } from './api'

const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws'

export interface WsEvent {
  event: string
  data: Record<string, unknown>
}

type Listener = (e: WsEvent) => void

// One socket per tab, shared by every subscriber. It opens with the first
// listener, reconnects while anyone is listening, and closes with the last.
const listeners = new Set<Listener>()
let socket: WebSocket | null = null
let retryTimer: ReturnType<typeof setTimeout> | null = null

function connect() {
  if (socket || listeners.size === 0) return
  const ws = new WebSocket(WS_URL)
  socket = ws
  // Per socket: an old socket closing late must not stop the new one's pings.
  let pingTimer: ReturnType<typeof setInterval> | null = null
  ws.onopen = () => {
    pingTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
    }, 25_000)
  }
  ws.onmessage = (msg) => {
    let parsed: WsEvent
    try {
      parsed = JSON.parse(msg.data)
    } catch {
      return // ignore malformed frames
    }
    if (parsed.event === 'pong') return
    for (const l of listeners) l(parsed)
  }
  ws.onclose = () => {
    if (pingTimer) clearInterval(pingTimer)
    pingTimer = null
    if (socket !== ws) return // replaced already; the current socket handles retries
    socket = null
    if (listeners.size > 0) retryTimer = setTimeout(connect, 3000)
  }
}

function disconnect() {
  if (retryTimer) clearTimeout(retryTimer)
  retryTimer = null
  const ws = socket
  socket = null
  ws?.close()
}

export function useWebSocket(onEvent: Listener) {
  const handlerRef = useRef(onEvent)
  useEffect(() => {
    handlerRef.current = onEvent
  })

  useEffect(() => {
    const listener: Listener = (e) => handlerRef.current(e)
    listeners.add(listener)
    connect()
    return () => {
      listeners.delete(listener)
      if (listeners.size === 0) disconnect()
    }
  }, [])
}
