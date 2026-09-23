import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { api } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { useWebSocket } from '../../lib/ws'
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
  const now = new Date()
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() + 1 })
  const [day, setDay] = useState<string | null>(null)
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

  if (!user) {
    return (
      <div className="earn-screen">
        <h1 className="earn-title">Earnings</h1>
        <p className="earn-note">Sign in to see who reports when, with Paula's read on each.</p>
      </div>
    )
  }

  return (
    <div className="earn-screen">
      <header className="earn-head">
        <h1 className="earn-title">{label}</h1>
        <div className="earn-nav">
          <button onClick={() => shift(-1)} aria-label="Previous month">
            ←
          </button>
          <button onClick={() => setYm({ y: now.getFullYear(), m: now.getMonth() + 1 })}>today</button>
          <button onClick={() => shift(1)} aria-label="Next month">
            →
          </button>
          <button onClick={rebuild} disabled={!!building}>
            {building
              ? building.total
                ? `rebuilding ${Math.round((building.done / building.total) * 100)}%`
                : 'rebuilding…'
              : 'rebuild'}
          </button>
        </div>
      </header>
      {month.data?.built_at && (
        <p className="earn-note">
          Calendar built {new Date(month.data.built_at).toLocaleString()}
          {month.data.stale && ' — stale; rebuild to pick up new dates'}
        </p>
      )}
      {month.error && <p className="earn-error">{month.error.message}</p>}

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
              <span className="earn-cell-d mono">{d}</span>
              {rows.length > 0 && (
                <>
                  <span className="earn-cell-tickers mono">{biggest.map((r) => r.ticker).join(' ')}</span>
                  <span className="earn-cell-count">{rows.length} reporting</span>
                </>
              )}
            </button>
          )
        })}
      </div>

      {day && (
        <section className="earn-day">
          <h2 className="earn-day-title">
            {new Date(day + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
          </h2>
          {dayQ.isPending ? (
            <p className="earn-note">Scoring each name…</p>
          ) : dayQ.error ? (
            <p className="earn-error">{dayQ.error.message}</p>
          ) : (
            <table className="earn-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Company</th>
                  <th className="num">Mkt cap</th>
                  <th>Read</th>
                </tr>
              </thead>
              <tbody>
                {dayQ.data.stocks.map((s) => (
                  <tr key={s.ticker}>
                    <td className="mono earn-ticker">{s.ticker}</td>
                    <td className="earn-company">{s.company}</td>
                    <td className="num mono">{cap(s.market_cap)}</td>
                    <td>
                      <span className={'earn-verdict earn-verdict-' + s.verdict}>{s.verdict}</span>
                      <span className="earn-reason">{s.reason}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  )
}
