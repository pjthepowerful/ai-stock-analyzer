import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { useChrome } from '../../lib/chrome'
import { useWebSocket } from '../../lib/ws'
import { IdeasPanel } from './IdeasPanel'
import './earnings.css'

interface CalRow {
  ticker: string
  company: string
  market_cap: number | null
  eps_estimate: number | null
  hour: string | null
}

interface MonthResponse {
  year: number
  month: number
  dates: Record<string, CalRow[]>
  built_at: string | null
  stale: boolean
}

interface DayStock extends CalRow {
  verdict: 'candidate' | 'watch' | 'blocked' | 'fade' | 'skip' | 'stale' | string
  reason: string
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

function iso(y: number, m: number, d: number) {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function cap(n: number | null) {
  if (!n) return '—'
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  return `$${(n / 1e6).toFixed(0)}M`
}

/** Weekday cells for a month, Monday-first, padded with nulls. */
function weekdayGrid(year: number, month: number): (number | null)[] {
  const days = new Date(year, month, 0).getDate()
  const cells: (number | null)[] = []
  const firstDow = (new Date(year, month - 1, 1).getDay() + 6) % 7 // Mon=0
  for (let i = 0; i < Math.min(firstDow, 5); i++) cells.push(null)
  for (let d = 1; d <= days; d++) {
    const dow = (new Date(year, month - 1, d).getDay() + 6) % 7
    if (dow < 5) cells.push(d)
  }
  while (cells.length % 5) cells.push(null)
  return cells
}

export function EarningsScreen() {
  const { user } = useSession()
  const { analyze } = useChrome()
  const now = new Date()
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() + 1 })
  const [day, setDay] = useState<string | null>(null)
  const [mode, setMode] = useState<'calendar' | 'ideas'>('calendar')
  const todayIso = iso(now.getFullYear(), now.getMonth() + 1, now.getDate())
  const qc = useQueryClient()
  const [building, setBuilding] = useState<{ done: number; total: number } | null>(null)

  useWebSocket((e) => {
    if (e.event === 'work_progress' && e.data.channel === 'calendar') {
      setBuilding({ done: Number(e.data.done ?? 0), total: Number(e.data.total ?? 0) })
    }
    if (e.event === 'earnings' && e.data.status === 'calendar_built') {
      setBuilding(null)
      void qc.invalidateQueries({ queryKey: ['earnings-month'] })
      void qc.invalidateQueries({ queryKey: ['earnings-day'] })
    }
  })

  async function rebuild() {
    setBuilding({ done: 0, total: 0 })
    try {
      await api.post('/api/earnings/calendar/refresh')
    } catch {
      setBuilding(null)
    }
  }

  const month = useQuery({
    queryKey: ['earnings-month', ym.y, ym.m],
    queryFn: () => api.get<MonthResponse>(`/api/earnings/calendar/month?year=${ym.y}&month=${ym.m}`),
    enabled: !!user,
  })
  const dayQ = useQuery({
    queryKey: ['earnings-day', day],
    queryFn: () => api.get<{ stocks: DayStock[] }>(`/api/earnings/calendar/day?date=${day}`),
    enabled: !!user && !!day,
    staleTime: 5 * 60_000,
  })

  const cells = useMemo(() => weekdayGrid(ym.y, ym.m), [ym])
  const label = new Date(ym.y, ym.m - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })

  function shift(delta: number) {
    const d = new Date(ym.y, ym.m - 1 + delta, 1)
    setYm({ y: d.getFullYear(), m: d.getMonth() + 1 })
    setDay(null)
  }

  const verdictBadge = (v: string) =>
    v === 'candidate' ? 'badge-green' : v === 'watch' ? 'badge-amber' : v === 'blocked' || v === 'fade' ? 'badge-red' : ''

  const head = (
    <header className="page-head">
      <div>
        <h1 className="page-title">Earnings</h1>
        <p className="page-sub">Who reports when, and Paula’s read on each</p>
      </div>
      {user && (
        <div className="seg" role="tablist" aria-label="View">
          {(['calendar', 'ideas'] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              className={'seg-btn' + (mode === m ? ' seg-on' : '')}
              onClick={() => setMode(m)}
            >
              {m === 'calendar' ? 'Calendar' : 'Ideas'}
            </button>
          ))}
        </div>
      )}
    </header>
  )

  if (!user) {
    return (
      <div className="page">
        <div className="page-inner">
          {head}
          <p className="card empty">Sign in to see the earnings calendar and Paula’s read on each report.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-inner">
        {head}

        {mode === 'ideas' ? (
          <IdeasPanel />
        ) : (
          <>
            <section className="card">
              <header className="card-head">
                <div>
                  <h2 className="card-title">{label}</h2>
                  <p className="card-desc">
                    {month.data?.built_at
                      ? `Calendar built ${new Date(month.data.built_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}${month.data.stale ? ' · stale' : ''}`
                      : 'Loading…'}
                  </p>
                </div>
                <div className="page-actions">
                  <button className="btn btn-secondary btn-sm btn-icon" onClick={() => shift(-1)} aria-label="Previous month">
                    <ChevronLeft size={15} />
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => setYm({ y: now.getFullYear(), m: now.getMonth() + 1 })}
                  >
                    Today
                  </button>
                  <button className="btn btn-secondary btn-sm btn-icon" onClick={() => shift(1)} aria-label="Next month">
                    <ChevronRight size={15} />
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={rebuild} disabled={!!building}>
                    <RefreshCw size={13} className={building ? 'spin' : undefined} />
                    {building
                      ? building.total
                        ? `${Math.round((building.done / building.total) * 100)}%`
                        : 'Rebuilding'
                      : 'Rebuild'}
                  </button>
                </div>
              </header>
              {month.error && <p className="note-warn earn-err">{month.error.message}</p>}

              <div className="card-body">
                <div className="earn-grid" role="grid">
                  {WEEKDAYS.map((w) => (
                    <div key={w} className="earn-dow">
                      {w}
                    </div>
                  ))}
                  {cells.map((d, i) => {
                    if (d == null) return <div key={`x${i}`} className="earn-cell earn-cell-pad" />
                    const key = iso(ym.y, ym.m, d)
                    const rows = month.data?.dates[key] ?? []
                    const biggest = [...rows].sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0)).slice(0, 3)
                    return (
                      <button
                        key={key}
                        className={
                          'earn-cell' +
                          (key === day ? ' earn-cell-on' : '') +
                          (key === todayIso ? ' earn-cell-today' : '') +
                          (rows.length ? '' : ' earn-cell-empty')
                        }
                        onClick={() => rows.length && setDay(key)}
                        disabled={!rows.length}
                      >
                        <span className="earn-cell-d">{d}</span>
                        {rows.length > 0 && (
                          <>
                            <span className="earn-cell-tickers">{biggest.map((r) => r.ticker).join(' · ')}</span>
                            <span className="earn-cell-count">
                              {rows.length}
                              <span className="earn-cell-count-word"> reporting</span>
                            </span>
                          </>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            </section>

            {day && (
              <section className="card">
                <header className="card-head">
                  <div>
                    <h2 className="card-title">
                      {new Date(day + 'T12:00:00').toLocaleDateString(undefined, {
                        weekday: 'long',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </h2>
                    <p className="card-desc">
                      {dayQ.data ? `${dayQ.data.stocks.length} companies reporting` : 'Scoring each name…'}
                    </p>
                  </div>
                </header>
                <div className="card-body-flush">
                  {dayQ.isPending ? (
                    <p className="empty">Scoring each name…</p>
                  ) : dayQ.error ? (
                    <p className="empty">{dayQ.error.message}</p>
                  ) : (
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Symbol</th>
                          <th className="earn-col-company">Company</th>
                          <th className="num">Market cap</th>
                          <th>Paula’s read</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dayQ.data.stocks.map((st) => (
                          <tr key={st.ticker}>
                            <td className="earn-ticker">
                              <button className="ticker-link" onClick={() => analyze(st.ticker)}>
                                {st.ticker}
                              </button>
                            </td>
                            <td className="earn-col-company text-dim">{st.company}</td>
                            <td className="num">{cap(st.market_cap)}</td>
                            <td>
                              <span className={'badge ' + verdictBadge(st.verdict)}>{st.verdict}</span>
                              <span className="earn-reason">{st.reason}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}
