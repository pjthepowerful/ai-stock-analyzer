import { useQuery } from '@tanstack/react-query'
import { AreaSeries, createChart, type UTCTimestamp } from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { chartColors, useTheme, withAlpha } from '../../lib/theme'

type Period = '1D' | '1W' | '1M' | '3M' | '6M' | '1A'
const PERIODS: { id: Period; label: string }[] = [
  { id: '1D', label: '1D' },
  { id: '1W', label: '1W' },
  { id: '1M', label: '1M' },
  { id: '3M', label: '3M' },
  { id: '6M', label: '6M' },
  { id: '1A', label: '1Y' },
]

interface Recap {
  start: string
  buys: number
  sells: number
  tickers: string[]
  pnl: number | null
}

interface PerformanceResponse {
  bucket: 'day' | 'week' | 'month'
  curve: { ts: number; equity: number; pnl: number }[]
  recaps: Recap[]
}

function recapLabel(start: string, bucket: PerformanceResponse['bucket']) {
  const d = new Date(start + 'T12:00:00')
  if (bucket === 'month') return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  const day = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return bucket === 'week' ? `Week of ${day}` : d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

function money(n: number) {
  const r = Math.round(n)
  if (r === 0) return '$0'
  return `${r > 0 ? '+' : '−'}$${Math.abs(r).toLocaleString()}`
}

function tone(n: number) {
  const r = Math.round(n)
  return r > 0 ? 'positive' : r < 0 ? 'negative' : ''
}

export function Performance() {
  const [period, setPeriod] = useState<Period>('1M')
  const perf = useQuery({
    queryKey: ['performance', period],
    queryFn: () => api.get<PerformanceResponse>(`/api/portfolio/performance?period=${period}`),
  })

  const curve = perf.data?.curve ?? []
  const first = curve[0]?.equity
  const last = curve[curve.length - 1]?.equity
  const change = first && last ? last - first : null
  const changePct = first && change != null ? (change / first) * 100 : null

  return (
    <>
      <section className="card">
        <header className="card-head">
          <div>
            <h2 className="card-title">Performance</h2>
            <p className={'card-desc ' + (change != null ? tone(change) : '')}>
              {change != null && changePct != null
                ? `${money(change)} (${change >= 0 ? '+' : ''}${changePct.toFixed(2)}%) over this range`
                : 'Account value over time'}
            </p>
          </div>
          <div className="seg" role="tablist" aria-label="Range">
            {PERIODS.map((p) => (
              <button
                key={p.id}
                role="tab"
                aria-selected={period === p.id}
                className={'seg-btn' + (period === p.id ? ' seg-on' : '')}
                onClick={() => setPeriod(p.id)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </header>
        <div className="card-body">
          {perf.isPending ? (
            <div className="perf-chart perf-chart-empty">Loading…</div>
          ) : curve.length < 2 ? (
            <div className="perf-chart perf-chart-empty">
              {perf.error ? perf.error.message : 'Not enough history for this range yet.'}
            </div>
          ) : (
            <EquityCurve points={curve} up={(change ?? 0) >= 0} />
          )}
        </div>
      </section>

      <section className="card">
        <header className="card-head">
          <div>
            <h2 className="card-title">Activity</h2>
            <p className="card-desc">Filled orders, grouped by {perf.data?.bucket ?? 'period'}</p>
          </div>
        </header>
        <div className="card-body-flush">
          {!perf.data || perf.data.recaps.length === 0 ? (
            <p className="empty">{perf.isPending ? 'Loading…' : 'No filled orders in this range.'}</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Orders</th>
                  <th>Symbols</th>
                  <th className="num">P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {perf.data.recaps.map((r) => (
                  <tr key={r.start}>
                    <td>{recapLabel(r.start, perf.data.bucket)}</td>
                    <td className="text-dim">
                      {r.buys} buy{r.buys === 1 ? '' : 's'} · {r.sells} sell{r.sells === 1 ? '' : 's'}
                    </td>
                    <td className="activity-syms">{r.tickers.join(', ')}</td>
                    <td className={'num ' + (r.pnl != null ? tone(r.pnl) : '')}>{r.pnl != null ? money(r.pnl) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </>
  )
}

function EquityCurve({ points, up }: { points: PerformanceResponse['curve']; up: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const [theme] = useTheme()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const c = chartColors()
    const chart = createChart(el, {
      height: 240,
      layout: { background: { color: 'transparent' }, textColor: c.text, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: c.grid } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      handleScroll: false,
      handleScale: false,
    })
    const line = up ? c.up : c.down
    const series = chart.addSeries(AreaSeries, {
      lineColor: line,
      lineWidth: 2,
      topColor: withAlpha(line, 0.18),
      bottomColor: withAlpha(line, 0),
      priceLineVisible: false,
    })
    // Alpaca can repeat a timestamp at session edges; the chart requires
    // strictly increasing times.
    const seen = new Set<number>()
    series.setData(
      points
        .filter((p) => (seen.has(p.ts) ? false : (seen.add(p.ts), true)))
        .map((p) => ({ time: p.ts as UTCTimestamp, value: p.equity })),
    )
    chart.timeScale().fitContent()

    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }))
    ro.observe(el)
    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [points, up, theme])

  return <div className="perf-chart" ref={ref} />
}
