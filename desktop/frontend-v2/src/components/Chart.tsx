import {
  CandlestickSeries,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { chartColors, useTheme, withAlpha } from '../lib/theme'
import './Chart.css'

interface ChartApiResponse {
  ok: boolean
  data?: {
    dates: string[]
    open: number[]
    high: number[]
    low: number[]
    close: number[]
    volume: number[]
  }
  error?: string
}

const PERIODS: [string, string][] = [
  ['1mo', '1M'],
  ['3mo', '3M'],
  ['6mo', '6M'],
  ['1y', '1Y'],
  ['5y', '5Y'],
]

const PERIOD_NAMES: Record<string, string> = {
  '1mo': 'past month',
  '3mo': 'past 3 months',
  '6mo': 'past 6 months',
  '1y': 'past year',
  '5y': 'past 5 years',
}

interface Legend {
  date: string
  o: number
  h: number
  l: number
  c: number
  chg: number
  chgPct: number
  /** Return from the first bar of the period to this bar. */
  fromStartPct: number
  hovering: boolean
}

function legendAt(d: NonNullable<ChartApiResponse['data']>, i: number, hovering: boolean): Legend {
  const prev = i > 0 ? d.close[i - 1] : d.close[i]
  const first = d.close[0]
  return {
    date: d.dates[i].split(' ')[0],
    o: d.open[i],
    h: d.high[i],
    l: d.low[i],
    c: d.close[i],
    chg: d.close[i] - prev,
    chgPct: prev ? ((d.close[i] - prev) / prev) * 100 : 0,
    fromStartPct: first ? ((d.close[i] - first) / first) * 100 : 0,
    hovering,
  }
}

function fmtDate(iso: string): string {
  const d = new Date(iso + 'T12:00:00')
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

const signed = (n: number, digits = 2) => (n >= 0 ? '+' : '') + n.toFixed(digits)

function calcSMA(data: number[], period: number): number[] {
  const r: number[] = []
  for (let i = period - 1; i < data.length; i++) {
    let s = 0
    for (let j = 0; j < period; j++) s += data[i - j]
    r.push(Math.round((s / period) * 100) / 100)
  }
  return r
}

function calcEMA(data: number[], period: number): number[] {
  const k = 2 / (period + 1)
  const r = [data[0]]
  for (let i = 1; i < data.length; i++) r.push(data[i] * k + r[i - 1] * (1 - k))
  return r.slice(period - 1).map((v) => Math.round(v * 100) / 100)
}

export function Chart({ ticker, height = 320 }: { ticker: string; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [period, setPeriod] = useState('1y')
  const [error, setError] = useState<string | null>(null)
  const [theme] = useTheme()
  const [ohlc, setOhlc] = useState<Legend | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    setError(null)
    const c = chartColors()

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      // Shorter on phones so the chart doesn't fill the whole screen.
      height: Math.min(height, Math.max(220, Math.round(containerRef.current.clientWidth * 0.72))),
      layout: { background: { color: 'transparent' }, textColor: c.text, fontFamily: "'Geist Mono', ui-monospace, monospace", fontSize: 11 },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, timeVisible: period === '1mo' },
    })
    chartRef.current = chart

    const candles: ISeriesApi<'Candlestick'> = chart.addSeries(CandlestickSeries, {
      upColor: c.up,
      downColor: c.down,
      borderUpColor: c.up,
      borderDownColor: c.down,
      wickUpColor: c.up,
      wickDownColor: c.down,
    })
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' })
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })

    let cancelled = false

    api
      .get<ChartApiResponse>(`/api/chart/${ticker}?period=${period}`)
      .then((res) => {
        // React 18 StrictMode double-invokes this effect in dev, so a stale
        // (cancelled) instance's fetch can resolve after a fresh one already
        // took over — bail silently rather than surfacing its result as an
        // error on top of the chart the live instance just rendered.
        if (cancelled) return
        if (!res.ok || !res.data) {
          setError(res.error || 'No chart data available.')
          return
        }
        const { dates, open, high, low, close, volume: vol } = res.data
        const times = dates.map((d) => d.split(' ')[0]) as unknown as Time[]

        const candleData = dates.map((_, i) => ({ time: times[i], open: open[i], high: high[i], low: low[i], close: close[i] }))
        const volData = dates.map((_, i) => ({
          time: times[i],
          value: vol[i],
          color: withAlpha(close[i] >= open[i] ? c.up : c.down, 0.25),
        }))

        candles.setData(candleData)
        volume.setData(volData)

        if (close.length >= 20) {
          const sma20 = calcSMA(close, 20)
          const line = chart.addSeries(LineSeries, { color: c.sma, lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
          line.setData(sma20.map((v, i) => ({ time: times[times.length - sma20.length + i], value: v })))
        }
        if (close.length >= 9) {
          const ema9 = calcEMA(close, 9)
          const line = chart.addSeries(LineSeries, { color: c.ema, lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
          line.setData(ema9.map((v, i) => ({ time: times[times.length - ema9.length + i], value: v })))
        }

        chart.timeScale().fitContent()

        // The legend follows the crosshair (TradingView) and the period
        // return scrubs with it (Robinhood); leaving the chart snaps back to
        // the latest bar.
        const data = res.data
        const last = close.length - 1
        const index = new Map(times.map((t, i) => [String(t), i]))
        if (last >= 0) setOhlc(legendAt(data, last, false))
        chart.subscribeCrosshairMove((param) => {
          const i = param.time !== undefined ? index.get(String(param.time)) : undefined
          if (i === undefined || !param.point) {
            if (last >= 0) setOhlc(legendAt(data, last, false))
            return
          }
          setOhlc(legendAt(data, i, true))
        })
      })
      .catch(() => {
        if (!cancelled) setError('Could not load chart data.')
      })

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    }
    window.addEventListener('resize', handleResize)

    return () => {
      cancelled = true
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
    }
  }, [ticker, period, height, theme])

  return (
    <div className="pchart card">
      <div className="pchart-head">
        <span className="pchart-sym">{ticker}</span>
        {ohlc && (
          <>
            <span className={'pchart-return mono ' + (ohlc.fromStartPct >= 0 ? 'positive' : 'negative')}>
              {signed(ohlc.fromStartPct)}%
              <span className="pchart-return-label">
                {ohlc.hovering ? `to ${fmtDate(ohlc.date)}` : PERIOD_NAMES[period]}
              </span>
            </span>
            <span className="pchart-ohlc mono">
              O {ohlc.o.toFixed(2)} H {ohlc.h.toFixed(2)} L {ohlc.l.toFixed(2)} C{' '}
              <b className={ohlc.chg >= 0 ? 'positive' : 'negative'}>{ohlc.c.toFixed(2)}</b>{' '}
              <span className={ohlc.chg >= 0 ? 'positive' : 'negative'}>
                {signed(ohlc.chg)} ({signed(ohlc.chgPct)}%)
              </span>
            </span>
          </>
        )}
        <div className="pchart-spacer" />
        <div className="seg">
          {PERIODS.map(([p, label]) => (
            <button key={p} className={'seg-btn' + (period === p ? ' seg-on' : '')} onClick={() => setPeriod(p)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="pchart-canvas" />
      {error && <div className="pchart-error">{error}</div>}
    </div>
  )
}
