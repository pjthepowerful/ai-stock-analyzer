import { useQuery } from '@tanstack/react-query'
import { Clock, MessageSquare, Search, TrendingUp } from 'lucide-react'
import { useRef, useState } from 'react'
import { Chart } from '../../components/Chart'
import { SignalCard, type AnalyzeData } from '../../components/SignalCard'
import { api } from '../../lib/api'
import { useChrome } from '../../lib/chrome'
import { searchTickers } from '../../lib/tickers'
import { KeyStats, type Fundamentals } from './KeyStats'
import { ResearchPanel } from './ResearchPanel'
import './analyze.css'

interface AnalyzeApiResponse {
  ok: boolean
  data?: AnalyzeData & Fundamentals
}

const FALLBACK = ['AAPL', 'NVDA', 'MSFT', 'TSLA', 'AMZN', 'META', 'SPY']

interface Popular {
  ticker: string
  people: number
  trending: boolean
}
const RECENT_KEY = 'paula-v2-recent-tickers'

function readRecent(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]').slice(0, 6)
  } catch {
    return []
  }
}

function pushRecent(t: string) {
  try {
    const next = [t, ...readRecent().filter((x) => x !== t)].slice(0, 6)
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {
    /* storage blocked — recents just won't persist */
  }
}

interface Props {
  /** Set from elsewhere (e.g. the command palette) to analyze a ticker. */
  request?: { ticker: string; n: number } | null
}

export function AnalyzeScreen({ request }: Props) {
  const { askPaula } = useChrome()
  const [active, setActive] = useState<string | null>(request?.ticker ?? null)
  // A new request from elsewhere (command menu) replaces the current ticker.
  const [seenRequest, setSeenRequest] = useState(request)
  if (request !== seenRequest) {
    setSeenRequest(request)
    if (request?.ticker) setActive(request.ticker)
  }

  // Cached per ticker, so flipping back to one you just looked at is instant.
  const q = useQuery({
    queryKey: ['analyze', active],
    queryFn: async () => {
      const res = await api.get<AnalyzeApiResponse>(`/api/analyze/${active}`)
      if (!res.ok || !res.data) throw new Error(`No data for ${active}.`)
      pushRecent(active!)
      return { ...res.data, ticker: active! }
    },
    enabled: !!active,
    staleTime: 60_000,
    retry: false,
  })


  function lookup(t: string) {
    const clean = t.trim().toUpperCase()
    if (clean) setActive(clean)
  }

  // What people are actually looking up this week (server-side counts).
  const popular = useQuery({
    queryKey: ['popular-tickers'],
    queryFn: () => api.get<{ tickers: Popular[] }>('/api/tickers/popular?limit=8').then((r) => r.tickers),
    staleTime: 60_000,
  })
  const quick: Popular[] = popular.data ?? FALLBACK.map((t) => ({ ticker: t, people: 0, trending: false }))
  const anyTrending = quick.some((p) => p.trending)

  const result = q.data ?? null
  const recent = result ? [] : readRecent()

  return (
    <div className="page">
      <div className="page-inner">
        <header className="page-head">
          <div>
            <h1 className="page-title">Analyze</h1>
            <p className="page-sub">Signal, levels, chart and research for any US ticker</p>
          </div>
          <TickerSearch onPick={lookup} busy={q.isFetching} autoFocus={!request} current={active} />
        </header>

        {q.error && <p className="note-warn">{q.error.message}</p>}

        {result ? (
          <>
            <div className="analyze-grid">
              <Chart ticker={result.ticker} height={380} />
              <SignalCard data={result} />
            </div>
            <KeyStats data={result} />
            <ResearchPanel ticker={result.ticker} />
            <div className="analyze-ask">
              <span>Want the reasoning behind this read?</span>
              <button
                className="btn btn-secondary"
                onClick={() => askPaula(`What's your take on ${result.ticker} right now? Walk me through the setup.`)}
              >
                <MessageSquare size={15} />
                Ask Paula about {result.ticker}
              </button>
            </div>
          </>
        ) : q.isFetching ? (
          <div className="analyze-grid">
            <div className="card skeleton" style={{ height: 432 }} />
            <div className="card skeleton" style={{ height: 432 }} />
          </div>
        ) : (
          <section className="card analyze-empty">
            <p className="analyze-empty-title">Pick a ticker to start</p>
            <p className="text-dim">The same signal engine Paula uses in chat, with the full breakdown.</p>
            {recent.length > 0 && (
              <>
                <p className="analyze-quick-label">
                  <Clock size={12} /> Recent
                </p>
                <div className="analyze-quick">
                  {recent.map((t) => (
                    <button key={t} className="btn btn-secondary btn-sm" onClick={() => lookup(t)}>
                      {t}
                    </button>
                  ))}
                </div>
              </>
            )}
            <p className="analyze-quick-label">
              {anyTrending ? (
                <>
                  <TrendingUp size={12} /> Trending on Paula this week
                </>
              ) : (
                'Popular'
              )}
            </p>
            <div className="analyze-quick">
              {quick.map((p) => (
                <button
                  key={p.ticker}
                  className={'btn btn-secondary btn-sm' + (p.trending ? ' quick-trending' : '')}
                  onClick={() => lookup(p.ticker)}
                  title={p.trending ? `${p.people} ${p.people === 1 ? 'person' : 'people'} looked this up this week` : undefined}
                >
                  {p.trending && <TrendingUp size={12} />}
                  {p.ticker}
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

function TickerSearch({
  onPick,
  busy,
  autoFocus,
  current,
}: {
  onPick: (t: string) => void
  busy: boolean
  autoFocus: boolean
  current: string | null
}) {
  const [value, setValue] = useState(current ?? '')
  // Show whatever is being analyzed, including picks from the command menu.
  const [shown, setShown] = useState(current)
  if (current !== shown) {
    setShown(current)
    setValue(current ?? '')
  }
  const [open, setOpen] = useState(false)
  const [hi, setHi] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const matches = searchTickers(value)

  function pick(t: string) {
    onPick(t)
    setValue(t)
    setOpen(false)
    inputRef.current?.blur()
  }

  return (
    <form
      className="analyze-search"
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        const chosen = open && matches[hi] ? matches[hi][0] : value
        if (chosen.trim()) pick(chosen.trim().toUpperCase())
      }}
    >
      <Search size={15} className="analyze-search-icon" />
      <input
        ref={inputRef}
        className="input analyze-input"
        value={value}
        onChange={(e) => {
          setValue(e.target.value.toUpperCase())
          setOpen(true)
          setHi(0)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (!open || matches.length === 0) return
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setHi((h) => (h + 1) % matches.length)
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setHi((h) => (h - 1 + matches.length) % matches.length)
          } else if (e.key === 'Escape') {
            setOpen(false)
          }
        }}
        placeholder="Ticker or company, e.g. Nvidia"
        aria-label="Ticker or company"
        role="combobox"
        aria-expanded={open && matches.length > 0}
        aria-controls="ticker-suggestions"
        aria-autocomplete="list"
        autoComplete="off"
        spellCheck={false}
        autoFocus={autoFocus}
      />
      <button className="btn btn-primary" type="submit" disabled={busy || !value.trim()}>
        {busy ? 'Analyzing…' : 'Analyze'}
      </button>

      {open && matches.length > 0 && (
        <ul className="ticker-menu" id="ticker-suggestions" role="listbox">
          {matches.map(([t, n], i) => (
            <li
              key={t}
              role="option"
              aria-selected={i === hi}
              className={'ticker-opt' + (i === hi ? ' ticker-opt-on' : '')}
              onMouseEnter={() => setHi(i)}
              onMouseDown={(e) => {
                e.preventDefault()
                pick(t)
              }}
            >
              <span className="ticker-opt-sym">{t}</span>
              <span className="ticker-opt-name">{n}</span>
            </li>
          ))}
        </ul>
      )}
    </form>
  )
}
