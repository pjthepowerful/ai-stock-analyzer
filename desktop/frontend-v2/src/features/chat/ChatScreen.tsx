import { Activity, ArrowUp, ChartCandlestick, Lightbulb, Wallet, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type ChatMessage, type ChatResponse } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { NEW_TITLE, useChats } from '../../lib/chats'
import { useChrome } from '../../lib/chrome'
import { Typewriter } from '../../components/Typewriter'
import { MarketStrip } from './MarketStrip'
import { Snapshot } from './Snapshot'
import { MessageBubble } from './MessageBubble'
import './chat.css'

// Cycled under the greeting, as in the original app.
const PHRASES = [
  'What are we trading today?',
  'What’s the play today?',
  'Let’s find some setups.',
  'What are we watching?',
  'What’s on your radar?',
  'Ready to make some moves?',
]

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
        const card = res.trade_signal && res.quote ? { ...res.quote, signal: res.trade_signal } : undefined
        append(chatId, {
          role: 'assistant',
          content: res.message,
          meta: { taste: res.taste, limitReached: res.limit_reached, card },
        })
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Something went wrong reaching Paula.'
      append(chatId, { role: 'assistant', content: msg })
    } finally {
      setSendingChat(null)
    }
  }

  const firstName = (user?.username ?? '').split(' ')[0]
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const busy = sendingChat !== null

  const suggestions: { icon: LucideIcon; title: string; desc: string; run: () => void }[] = [
    {
      icon: Lightbulb,
      title: 'What should I buy?',
      desc: 'Scan the market for setups that clear the full bar',
      run: () => send('What should I invest in right now? Give me your real take.'),
    },
    {
      icon: Activity,
      title: 'How is the market today?',
      desc: 'Regime, breadth and what’s moving',
      run: () => send('How is the market looking today?'),
    },
    {
      icon: ChartCandlestick,
      title: 'Analyze a stock',
      desc: 'Signal, levels, chart and earnings for any ticker',
      run: onNavigateAnalyze,
    },
    {
      icon: Wallet,
      title: 'How did I do today?',
      desc: 'A recap of your positions and P&L',
      run: () => send('How did we do today?'),
    },
  ]

  return (
    <div className="chat">
      <MarketStrip />

      <div className="chat-scroll" ref={listRef}>
        <div className="chat-column">
          {messages.length === 0 ? (
            <div className="chat-empty">
              <span className="chat-empty-mark">P</span>
              <h1 className="chat-hello">
                {greeting}
                {firstName && `, ${firstName}`}
              </h1>
              <p className="chat-hello-sub">
                <Typewriter phrases={PHRASES} />
              </p>
              <Snapshot />
              <div className="chat-suggest">
                {suggestions.map(({ icon: Icon, title, desc, run }) => (
                  <button key={title} className="suggest" onClick={run} disabled={busy}>
                    <Icon size={16} strokeWidth={1.8} />
                    <span className="suggest-title">{title}</span>
                    <span className="suggest-desc">{desc}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((m, i) => (
                <MessageBubble key={i} role={m.role} content={m.content} meta={m.meta} />
              ))}

              {sending && (
                <div className="msg msg-assistant">
                  <span className="msg-avatar">P</span>
                  <div className="msg-thinking" aria-label="Paula is thinking">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}

              {scanHere && (
                <div className="msg msg-assistant">
                  <span className="msg-avatar">P</span>
                  <div className="scan">
                    <div className="scan-label">
                      <span>{scanHere.label ? `Scanning — ${scanHere.label}` : 'Scanning the market…'}</span>
                      <span className="mono">{Math.round(scanHere.pct)}%</span>
                    </div>
                    <div className="scan-track">
                      <div className="scan-fill" style={{ width: `${scanHere.pct}%` }} />
                    </div>
                  </div>
                </div>
              )}

              {!sending && !scanHere && (
                <button
                  className="chat-report"
                  onClick={() => openReport(messages.map((m) => ({ role: m.role, content: m.content })))}
                >
                  Something off? Report this chat
                </button>
              )}
            </>
          )}
        </div>
      </div>

      <div className="composer-wrap">
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
        >
          <textarea
            className="composer-input"
            value={input}
            rows={1}
            onChange={(e) => {
              setInput(e.target.value)
              // Grow with the text, up to a few lines.
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Message Paula…"
            disabled={busy}
          />
          <button className="composer-send" type="submit" disabled={busy || !input.trim()} aria-label="Send">
            <ArrowUp size={16} strokeWidth={2.2} />
          </button>
        </form>
        <p className="composer-hint">Paula can be wrong. Research only — nothing here is an order.</p>
      </div>
    </div>
  )
}
