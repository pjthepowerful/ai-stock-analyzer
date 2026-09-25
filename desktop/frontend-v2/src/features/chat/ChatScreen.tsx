import { Activity, ArrowUp, CalendarDays, ChartCandlestick, ImagePlus, Lightbulb, Wallet, X, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, ApiError, FREE_DAILY_MESSAGES, type ChatMessage, type ChatResponse } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { NEW_TITLE, useChats } from '../../lib/chats'
import { useChrome } from '../../lib/chrome'
import { shrinkImage } from '../../lib/image'
import { Typewriter } from '../../components/Typewriter'
import { Snapshot } from './Snapshot'
import { MessageBubble } from './MessageBubble'
import { loadTier, ModelPicker, TIER_NAME, type ModelTier } from './ModelPicker'
import { describeTrade } from './TradeConfirm'
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
  /** Text handed over from elsewhere (e.g. Analyze's "Ask Paula"). */
  draft?: { text: string; n: number } | null
}

// Reply types that are about specific stocks, so a chart belongs with them.
const CHART_TYPES = new Set(['analysis', 'compare', 'list'])

function fallbackTitle(text: string) {
  return text.length <= 30 ? text : text.slice(0, 28).trimEnd() + '…'
}

export function ChatScreen({ onNavigateAnalyze, draft }: Props) {
  const { user, isGuest, refresh, signOut } = useSession()
  const { openReport, openPlus } = useChrome()
  const { active, append, patchMeta, rename, ensureActive, scan, startScan } = useChats()
  const [input, setInput] = useState(draft?.text ?? '')
  const [seenDraft, setSeenDraft] = useState(draft)
  if (draft !== seenDraft) {
    setSeenDraft(draft)
    if (draft) setInput(draft.text)
  }
  const [sendingChat, setSendingChat] = useState<string | null>(null)
  const [tier, setTier] = useState<ModelTier>(loadTier)
  // An attached chart or screenshot: the upload copy and a small preview.
  const [image, setImage] = useState<{ full: string; thumb: string } | null>(null)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  async function attach(file: File | null | undefined) {
    if (!file || !file.type.startsWith('image/')) return
    try {
      const [full, thumb] = await Promise.all([shrinkImage(file), shrinkImage(file, 360, 0.7)])
      setImage({ full, thumb })
    } catch {
      /* not a readable image — ignore */
    }
  }
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
    const pic = image
    const trimmed = text.trim() || (pic ? 'What do you see in this image?' : '')
    if (!trimmed || sendingChat) return
    const chatId = ensureActive()
    const history: ChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }))
    const isFirst = messages.length === 0

    setInput('')
    setImage(null)
    setSendingChat(chatId)
    append(chatId, { role: 'user', content: trimmed, meta: pic ? { image: pic.thumb } : undefined })
    if (isFirst && (active?.title ?? NEW_TITLE) === NEW_TITLE) void nameChat(chatId, trimmed)

    try {
      const res = await api.post<ChatResponse>('/api/chat', { message: trimmed, history, model: tier, image: pic?.full })
      if (res.type === 'scan_started') {
        startScan(chatId, res.scan_id ?? '')
      } else if (res.type === 'confirm_trade' && res.trade) {
        append(chatId, {
          role: 'assistant',
          content: `Confirm order: ${describeTrade(res.trade)}`,
          meta: { trade: res.trade, tradeState: 'pending' },
        })
      } else {
        const card = res.trade_signal && res.quote ? { ...res.quote, signal: res.trade_signal } : undefined
        // Stock analyses get a chart; the free "taste" keeps charts for Plus.
        const analyzed = CHART_TYPES.has(res.type) && !res.taste
        const tickers = (res.tickers?.length ? res.tickers : res.ticker ? [res.ticker] : []).filter(Boolean)
        const charts = analyzed && tickers.length ? tickers.slice(0, 6) : undefined
        append(chatId, {
          role: 'assistant',
          content: res.message,
          meta: {
            taste: res.taste,
            limitReached: res.limit_reached,
            card,
            charts,
            model: res.model ? `Paula ${TIER_NAME[tier]} · ${res.model}` : undefined,
          },
        })
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Something went wrong reaching Paula.'
      append(chatId, { role: 'assistant', content: msg })
    } finally {
      setSendingChat(null)
      if (user && !user.plus && !user.is_admin) void refresh()
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
    // Guests have no portfolio to recap; give them something that works.
    isGuest
      ? {
          icon: CalendarDays,
          title: 'Who reports earnings this week?',
          desc: 'The names on the calendar and Paula’s read',
          run: () => send('Who reports earnings this week?'),
        }
      : {
          icon: Wallet,
          title: 'How did I do today?',
          desc: 'A recap of your positions and P&L',
          run: () => send('How did we do today?'),
        },
  ]

  return (
    <div className="chat">
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
                <MessageBubble
                  key={i}
                  role={m.role}
                  content={m.content}
                  meta={m.meta}
                  onMeta={(meta) => active && patchMeta(active.id, i, meta)}
                />
              ))}

              {sending && (
                <div className="msg msg-assistant">
                  <span className="msg-avatar">P</span>
                  <div className="msg-thinking" role="status">
                    <span className="msg-thinking-text">Paula {TIER_NAME[tier]} is thinking…</span>
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
          className={'composer' + (dragging ? ' composer-drop' : '')}
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
          onDragOver={(e) => {
            if (e.dataTransfer.types.includes('Files')) {
              e.preventDefault()
              setDragging(true)
            }
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            void attach(e.dataTransfer.files[0])
          }}
        >
          {image && (
            <div className="composer-attach">
              <img src={image.thumb} alt="Attached image" />
              <button type="button" className="composer-attach-x" onClick={() => setImage(null)} aria-label="Remove image">
                <X size={12} strokeWidth={2.4} />
              </button>
            </div>
          )}
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
            onPaste={(e) => {
              const file = [...e.clipboardData.files].find((f) => f.type.startsWith('image/'))
              if (file) {
                e.preventDefault()
                void attach(file)
              }
            }}
            placeholder={image ? 'Ask about this image…' : 'Message Paula…'}
            disabled={busy}
          />
          <div className="composer-bar">
            <div className="composer-tools">
              <button
                type="button"
                className="composer-tool"
                onClick={() => fileRef.current?.click()}
                aria-label="Attach an image"
                title="Attach a chart or screenshot"
              >
                <ImagePlus size={16} strokeWidth={1.9} />
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                hidden
                onChange={(e) => {
                  void attach(e.target.files?.[0])
                  e.target.value = ''
                }}
              />
              <ModelPicker value={tier} onChange={setTier} />
            </div>
            <button className="composer-send" type="submit" disabled={busy || (!input.trim() && !image)} aria-label="Send">
              <ArrowUp size={16} strokeWidth={2.2} />
            </button>
          </div>
        </form>
        {user && !user.plus && !user.is_admin ? (
          // Free-tier line, as ChatGPT and Claude show it: what's left today
          // and a one-click way to lift the cap.
          <p className="composer-hint composer-quota">
            {(() => {
              const left = Math.max(0, FREE_DAILY_MESSAGES - (user.messages_today ?? 0))
              return left > 0
                ? `${left} of ${FREE_DAILY_MESSAGES} free messages left today`
                : 'You’ve used today’s free messages'
            })()}
            {' · '}
            <button className="composer-quota-cta" onClick={openPlus}>
              Get unlimited with Plus
            </button>
          </p>
        ) : isGuest ? (
          // Logged-out nudge, as ChatGPT does: quiet, one click to sign up.
          <p className="composer-hint composer-quota">
            Chatting as a guest{' · '}
            <button
              className="composer-quota-cta"
              onClick={() => {
                try {
                  sessionStorage.setItem('paula-auth-mode', 'signup')
                } catch {
                  /* lands on sign-in instead */
                }
                signOut()
              }}
            >
              Create a free account
            </button>{' '}
            to save your chats
          </p>
        ) : (
          <p className="composer-hint">Paula can be wrong. No order is placed until you confirm it.</p>
        )}
      </div>
    </div>
  )
}
