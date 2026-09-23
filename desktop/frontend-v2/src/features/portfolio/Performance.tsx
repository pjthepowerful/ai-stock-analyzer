import { useQuery } from '@tanstack/react-query'
import { AreaSeries, createChart, type UTCTimestamp } from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'

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
    <section className="perf">
      <div className="perf-head">
        <h2 className="portfolio-section-title">Performance</h2>
        <div className="perf-periods" role="tablist">
          {PERIODS.map((p) => (
            <button
              key={p.id}
              role="tab"
              aria-selected={period === p.id}
              className={'perf-period' + (period === p.id ? ' perf-period-on' : '')}
              onClick={() => setPeriod(p.id)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {change != null && changePct != null && (
        <p className={'perf-change mono ' + (change >= 0 ? 'positive' : 'negative')}>
          {money(change)} ({change >= 0 ? '+' : ''}
          {changePct.toFixed(2)}%)
        </p>
      )}

      {perf.isPending ? (
        <div className="perf-chart perf-chart-empty">Loading…</div>
      ) : curve.length < 2 ? (
        <div className="perf-chart perf-chart-empty">
          {perf.error ? perf.error.message : 'Not enough history for this range yet.'}
        </div>
      ) : (
        <EquityCurve points={curve} up={(change ?? 0) >= 0} />
      )}

      {perf.data && (
        <>
          <h3 className="perf-sub">Activity</h3>
          {perf.data.recaps.length === 0 ? (
            <p className="portfolio-empty">No filled orders in this range.</p>
          ) : (
            <ul className="perf-recaps">
              {perf.data.recaps.map((r) => (
                <li key={r.start} className="perf-recap">
                  <span className="perf-recap-when">{recapLabel(r.start, perf.data.bucket)}</span>
                  <span className="perf-recap-what">
                    <span className="mono">
                      {r.buys} buy{r.buys === 1 ? '' : 's'} · {r.sells} sell{r.sells === 1 ? '' : 's'}
                    </span>
                    <span className="perf-recap-tickers mono">{r.tickers.join(' ')}</span>
                  </span>
                  {r.pnl != null && (
                    <span className={'perf-recap-pnl mono ' + tone(r.pnl)}>{money(r.pnl)}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}

function EquityCurve({ points, up }: { points: PerformanceResponse['curve']; up: boolean }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const chart = createChart(el, {
      height: 220,
      layout: { background: { color: 'transparent' }, textColor: '#5a6068', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: 'rgba(35,38,44,0.5)' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      handleScroll: false,
      handleScale: false,
    })
    const line = up ? '#34d399' : '#f87171'
    const series = chart.addSeries(AreaSeries, {
      lineColor: line,
      lineWidth: 2,
      topColor: up ? 'rgba(52,211,153,0.18)' : 'rgba(248,113,113,0.18)',
      bottomColor: 'rgba(0,0,0,0)',
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
  }, [points, up])

  return <div className="perf-chart" ref={ref} />
}
