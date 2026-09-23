import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type ChatMessage, type ChatResponse } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { NEW_TITLE, useChats } from '../../lib/chats'
import { useChrome } from '../../lib/chrome'
import { ChatList } from './ChatList'
import { MarketStrip } from './MarketStrip'
import { MessageBubble } from './MessageBubble'
import './chat.css'

interface Props {
  onNavigateAnalyze: () => void
}

function fallbackTitle(text: string) {
  return text.length <= 30 ? text : text.slice(0, 28).trimEnd() + '…'
}

export function ChatScreen({ onNavigateAnalyze }: Props) {
  const { user, isGuest } = useSession()
  const { openReport } = useChrome()
  const { active, append, rename, ensureActive, scan, startScan } = useChats()
  const [input, setInput] = useState('')
  const [sendingChat, setSendingChat] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const messages = active?.messages ?? []
  const sending = sendingChat !== null && sendingChat === active?.id
  const scanHere = scan && scan.chatId === active?.id ? scan : null

  // Follow new messages and scan progress in the open chat.
  useEffect(() => {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
    })
  }, [messages.length, active?.id, scanHere?.pct])

  async function nameChat(chatId: string, firstMessage: string) {
    if (isGuest) {
      rename(chatId, fallbackTitle(firstMessage))
      return
    }
    try {
      const res = await api.post<{ title: string }>('/api/chat/title', { message: firstMessage })
      rename(chatId, res.title || fallbackTitle(firstMessage))
    } catch {
      rename(chatId, fallbackTitle(firstMessage))
    }
  }

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || sendingChat) return
    const chatId = ensureActive()
    const history: ChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }))
    const isFirst = messages.length === 0

    setInput('')
    setSendingChat(chatId)
    append(chatId, { role: 'user', content: trimmed })
    if (isFirst && (active?.title ?? NEW_TITLE) === NEW_TITLE) void nameChat(chatId, trimmed)

    try {
      const res = await api.post<ChatResponse>('/api/chat', { message: trimmed, history })
      if (res.type === 'scan_started') {
        startScan(chatId, res.scan_id ?? '')
      } else {
        append(chatId, {
          role: 'assistant',
          content: res.message,
          meta: { taste: res.taste, limitReached: res.limit_reached },
        })
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Something went wrong reaching Paula.'
      append(chatId, { role: 'assistant', content: msg })
    } finally {
      setSendingChat(null)
    }
  }

  const displayName = user?.username ?? 'Guest'

  return (
    <div className="chat-screen">
      <ChatList />

      <div className="chat-main">
        <MarketStrip />
        <div className="chat-body" ref={listRef}>
          {messages.length === 0 && (
            <div className="chat-empty">
              <h1 className="chat-greeting">Good to see you, {displayName}.</h1>
              <p className="chat-greeting-sub">What are we trading today?</p>
              <div className="chat-suggestions">
                <button className="chat-chip" onClick={() => send('What should I invest in right now? Give me your real take.')}>
                  What should I buy?
                </button>
                <button className="chat-chip" onClick={() => send('How is the market looking today?')}>
                  Check the market
                </button>
                <button className="chat-chip" onClick={onNavigateAnalyze}>
                  Analyze a stock
                </button>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <MessageBubble key={i} role={m.role} content={m.content} meta={m.meta} />
          ))}

          {sending && <div className="chat-thinking">Paula is thinking…</div>}

          {messages.length > 0 && !sending && !scanHere && (
            <button
              className="chat-report"
              onClick={() => openReport(messages.map((m) => ({ role: m.role, content: m.content })))}
            >
              Something off? Report this chat
            </button>
          )}

          {scanHere && (
            <div className="chat-scan">
              <div className="chat-scan-label">{scanHere.label || 'Scanning the market…'}</div>
              <div className="chat-scan-track">
                <div className="chat-scan-fill" style={{ width: `${scanHere.pct}%` }} />
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
            disabled={sendingChat !== null}
          />
          <button className="chat-send" type="submit" disabled={sendingChat !== null || !input.trim()}>
            →
          </button>
        </form>
      </div>
    </div>
  )
}
