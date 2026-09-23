import { useRef, useState } from 'react'
import { api, ApiError, type ChatMessage, type ChatResponse } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { useWebSocket, type WsEvent } from '../../lib/ws'
import { MessageBubble } from './MessageBubble'
import './chat.css'

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  meta?: { taste?: boolean; limitReached?: boolean; scanning?: boolean }
}

const SUGGESTIONS = ['What should I buy?', 'Check the market', 'Analyze a stock']

export function ChatScreen() {
  const { user, isGuest, signOut } = useSession()
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [scanProgress, setScanProgress] = useState<{ pct: number; label: string } | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useWebSocket((e: WsEvent) => {
    if (e.event === 'scan_progress') {
      setScanProgress({ pct: Number(e.data.pct ?? 0), label: String(e.data.label ?? '') })
    }
    if (e.event === 'scan_result') {
      setScanProgress(null)
      setMessages((prev) => [...prev, { role: 'assistant', content: String(e.data.message ?? '') }])
    }
  })

  function scrollToBottom() {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
    })
  }

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setInput('')
    setSending(true)

    const history: ChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }))
    setMessages((prev) => [...prev, { role: 'user', content: trimmed }])
    scrollToBottom()

    try {
      const res = await api.post<ChatResponse>('/api/chat', { message: trimmed, history })
      if (res.type === 'scan_started') {
        setScanProgress({ pct: 0, label: 'Starting…' })
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: res.message,
            meta: { taste: res.taste, limitReached: res.limit_reached },
          },
        ])
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Something went wrong reaching Paula.'
      setMessages((prev) => [...prev, { role: 'assistant', content: msg }])
    } finally {
      setSending(false)
      scrollToBottom()
    }
  }

  const displayName = user?.username ?? 'Guest'

  return (
    <div className="chat-screen">
      <header className="chat-header">
        <span className="chat-logo">P</span>
        <span className="chat-title">Paula</span>
        <span className="chat-badge">preview</span>
        <div className="chat-header-spacer" />
        <button className="chat-signout" onClick={signOut}>
          {isGuest ? 'Exit guest' : 'Sign out'}
        </button>
      </header>

      <div className="chat-body" ref={listRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <h1 className="chat-greeting">Good to see you, {displayName}.</h1>
            <p className="chat-greeting-sub">What are we trading today?</p>
            <div className="chat-suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chat-chip" onClick={() => send(s === 'What should I buy?' ? 'What should I invest in right now? Give me your real take.' : s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} content={m.content} meta={m.meta} />
        ))}

        {scanProgress && (
          <div className="chat-scan">
            <div className="chat-scan-label">{scanProgress.label || 'Scanning the market…'}</div>
            <div className="chat-scan-track">
              <div className="chat-scan-fill" style={{ width: `${scanProgress.pct}%` }} />
            </div>
          </div>
        )}
      </div>

      <form
        className="chat-input-row"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <input
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message Paula — ask for a setup, scan, or recap…"
          disabled={sending}
        />
        <button className="chat-send" type="submit" disabled={sending || !input.trim()}>
          →
        </button>
      </form>
    </div>
  )
}
