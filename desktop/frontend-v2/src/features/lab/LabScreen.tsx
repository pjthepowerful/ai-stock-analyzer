import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AreaSeries, createChart, LineStyle, type UTCTimestamp } from 'lightweight-charts'
import { Play, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { chartColors, useTheme, withAlpha } from '../../lib/theme'
import { useToast } from '../../lib/toast'
import './lab.css'

type ParamValue = string | number | boolean | null

interface ParamSpec {
  key: string
  label: string
  type: 'choice' | 'number' | 'int' | 'percent' | 'bool'
  options?: (string | number)[]
  min?: number
  max?: number
  step?: number
  unit?: string
  help?: string
}

interface Strategy {
  key: string
  label: string
  source: string
  summary: string
  live_mode: string | null
  params: ParamSpec[]
  defaults: Record<string, ParamValue>
  earliest: string
  published_through: string | null
}

interface Stats {
  days?: number
  trades?: number
  total_return_pct?: number
  cagr_pct?: number
  sharpe?: number
  max_drawdown_pct?: number
  win_rate_pct?: number | null
  profit_factor?: number | null
  avg_win?: number
  avg_loss?: number
  pct_days_green?: number
  worst_day_pct?: number
  best_day_pct?: number
}

interface Result extends Stats {
  by_year: Record<string, Stats>
  out_of_sample?: Stats & { from: string }
  benchmark?: Stats & { symbol: string }
}

interface Trade {
  day: string
  symbol: string
  side: 'long' | 'short'
  entry: number
  exit: number
  qty: number
  entry_time: string
  exit_time: string
  reason: string
  pnl: number
}

interface Run {
  id: string
  created_at: number
  strategy: string
  label: string | null
  start: string
  end: string
  params: Record<string, ParamValue>
  equity0: number
  result: Result
  equity_curve: [string, number][]
  trades: Trade[]
  trades_total: number
}

interface RunRow {
  id: string
  created_at: number
  strategy: string
  label: string | null
  start: string
  end: string
  total_return_pct?: number
  sharpe?: number
  max_drawdown_pct?: number
  trades?: number
}

interface Job {
  id: string | null
  status: 'idle' | 'running' | 'done' | 'error'
  progress: { done: number; total: number; day: string; equity: number } | null
  error: string | null
  request: { strategy: string; start: string; end: string } | null
}

const pct = (n: number | null | undefined, d = 1) =>
  n == null ? '—' : `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(d)}%`
const tone = (n: number | null | undefined) => (n == null ? '' : n > 0 ? 'positive' : n < 0 ? 'negative' : '')
const money = (n: number) => `${n < 0 ? '−' : ''}$${Math.abs(Math.round(n)).toLocaleString()}`

/** Pass bar for "worth paper-trading": risk-adjusted, survives out of sample, drawdown you can sit through. */
function verdict(r: Result): { pass: boolean; tone: 'positive' | 'warn' | 'negative'; title: string; reasons: string[] } {
  const reasons: string[] = []
  const oos = r.out_of_sample
  const sharpeOk = (r.sharpe ?? 0) >= 1
  const ddOk = (r.max_drawdown_pct ?? -100) > -20
  const pfOk = (r.profit_factor ?? 0) >= 1.1
  const oosOk = !oos || oos.days == null || oos.days < 60 || (oos.sharpe ?? 0) >= 0.5
  reasons.push(`Sharpe ${r.sharpe?.toFixed(2) ?? '—'} ${sharpeOk ? '≥' : '<'} 1.0`)
  reasons.push(`Max drawdown ${pct(r.max_drawdown_pct)} ${ddOk ? 'within' : 'beyond'} −20%`)
  reasons.push(`Profit factor ${r.profit_factor?.toFixed(2) ?? '—'} ${pfOk ? '≥' : '<'} 1.1`)
  if (oos && oos.days && oos.days >= 60)
    reasons.push(`After the paper (since ${oos.from.slice(0, 7)}): Sharpe ${oos.sharpe?.toFixed(2)} ${oosOk ? '≥' : '<'} 0.5`)
  const passed = [sharpeOk, ddOk, pfOk, oosOk].filter(Boolean).length
  if (passed === 4) return { pass: true, tone: 'positive', title: 'Passes the bar for paper trading', reasons }
  if ((r.total_return_pct ?? 0) > 0 && passed >= 2)
    return { pass: false, tone: 'warn', title: 'Made money, but not reliably enough', reasons }
  return { pass: false, tone: 'negative', title: 'No edge here', reasons }
}

export function LabScreen() {
  const qc = useQueryClient()
  const toast = useToast()
  const strategies = useQuery({
    queryKey: ['lab-strategies'],
    queryFn: () => api.get<{ strategies: Strategy[] }>('/api/lab/strategies'),
    staleTime: Infinity,
  })
  const runs = useQuery({
    queryKey: ['lab-runs'],
    queryFn: () => api.get<{ job: Job; runs: RunRow[] }>('/api/lab/runs'),
    refetchInterval: (q) => (q.state.data?.job.status === 'running' ? 1500 : false),
  })
  const [stratKey, setStratKey] = useState('noise')
  const [values, setValues] = useState<Record<string, ParamValue>>({})
  const [start, setStart] = useState('2022-01-03')
  const [end, setEnd] = useState(() => new Date().toISOString().slice(0, 10))
  const [equity, setEquity] = useState(25000)
  const [openId, setOpenId] = useState<string | null>(null)

  const strat = strategies.data?.strategies.find((s) => s.key === stratKey)
  const job = runs.data?.job
  const running = job?.status === 'running'

  // A run that just finished opens itself.
  const lastJob = useRef<string | null>(null)
  useEffect(() => {
    if (!job?.id) return
    if (lastJob.current === job.id + job.status) return
    const wasRunning = lastJob.current === job.id + 'running'
    lastJob.current = job.id + job.status
    if (wasRunning && job.status === 'done') setOpenId(job.id)
    if (wasRunning && job.status === 'error') toast.show(`Backtest failed: ${job.error ?? 'unknown error'}`)
  }, [job, toast])

  // Until one is picked, show the newest saved run.
  const shownId = openId ?? runs.data?.runs[0]?.id ?? null

  const detail = useQuery({
    queryKey: ['lab-run', shownId],
    queryFn: () => api.get<{ run: Run }>(`/api/lab/runs/${shownId}`),
    enabled: !!shownId,
    staleTime: Infinity,
  })

  const params = useMemo(() => ({ ...(strat?.defaults ?? {}), ...values }), [strat, values])

  const run = useMutation({
    mutationFn: () =>
      api.post<{ job: Job }>('/api/lab/run', { strategy: stratKey, start, end, equity, params }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lab-runs'] }),
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Could not start the backtest'),
  })

  async function remove(id: string) {
    await api.del(`/api/lab/runs/${id}`)
    if (shownId === id) setOpenId(null)
    qc.invalidateQueries({ queryKey: ['lab-runs'] })
  }

  function pick(key: string) {
    setStratKey(key)
    setValues({})
    const s = strategies.data?.strategies.find((x) => x.key === key)
    if (s && start < s.earliest) setStart(s.earliest)
  }

  const labels = Object.fromEntries((strategies.data?.strategies ?? []).map((s) => [s.key, s.label]))

  return (
    <div className="page">
      <div className="page-inner">
        <header className="page-head">
          <div>
            <h1 className="page-title">Backtest lab</h1>
            <p className="page-sub">
              Replay a day-trading strategy on real minute-by-minute market data — with commissions, slippage and
              pessimistic fills — before it trades a dollar.
            </p>
          </div>
        </header>

        <div className="lab-layout">
          <section className="card lab-config" aria-label="Backtest settings">
            <div className="card-body lab-config-body">
              <div className="lab-strats" role="radiogroup" aria-label="Strategy">
                {strategies.data?.strategies.map((s) => (
                  <button
                    key={s.key}
                    role="radio"
                    aria-checked={s.key === stratKey}
                    className={'lab-strat' + (s.key === stratKey ? ' lab-strat-on' : '')}
                    onClick={() => pick(s.key)}
                  >
                    <span className="lab-strat-name">
                      {s.label}
                      {s.live_mode && <span className="badge badge-green">Autopilot</span>}
                    </span>
                    <span className="lab-strat-src">{s.source.split(' — ')[0]}</span>
                  </button>
                ))}
                {strategies.isPending && <p className="text-dim">Loading strategies…</p>}
                {strategies.error && <p className="negative">{strategies.error.message}</p>}
              </div>

              {strat && (
                <>
                  <p className="lab-summary">{strat.summary}</p>
                  <div className="lab-fields">
                    {strat.params.map((p) => (
                      <Field key={p.key} spec={p} value={params[p.key]} onChange={(v) => setValues({ ...values, [p.key]: v })} />
                    ))}
                  </div>
                  <div className="lab-fields lab-fields-3">
                    <label className="lab-field">
                      <span className="lab-field-label">From</span>
                      <input className="input" type="date" value={start} min={strat.earliest} onChange={(e) => setStart(e.target.value)} />
                    </label>
                    <label className="lab-field">
                      <span className="lab-field-label">To</span>
                      <input className="input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
                    </label>
                    <label className="lab-field">
                      <span className="lab-field-label">Starting equity</span>
                      <input
                        className="input mono"
                        type="number"
                        min={1000}
                        step={1000}
                        value={equity}
                        onChange={(e) => setEquity(Number(e.target.value))}
                      />
                    </label>
                  </div>
                  <button className="btn btn-primary lab-run" onClick={() => run.mutate()} disabled={running || run.isPending}>
                    <Play size={14} />
                    {running ? 'Running…' : 'Run backtest'}
                  </button>
                  {running && job?.progress && (
                    <div className="lab-progress" role="status">
                      <div className="lab-progress-bar">
                        <span style={{ width: `${(job.progress.done / job.progress.total) * 100}%` }} />
                      </div>
                      <span className="mono text-dim">
                        {job.progress.day} · {money(job.progress.equity)}
                      </span>
                    </div>
                  )}
                  {running && !job?.progress && <p className="text-dim lab-note">Fetching market data…</p>}
                  <p className="lab-note text-dim">
                    First runs download history from Alpaca and can take several minutes; re-runs use the cache.
                  </p>
                </>
              )}
            </div>
          </section>

          <div className="lab-results">
            {detail.data ? (
              <Results run={detail.data.run} label={labels[detail.data.run.strategy] ?? detail.data.run.strategy} />
            ) : (
              <section className="card">
                <p className="empty">{detail.isFetching ? 'Loading…' : 'Run a backtest to see results here.'}</p>
              </section>
            )}

            {!!runs.data?.runs.length && (
              <section className="card">
                <header className="card-head">
                  <h2 className="card-title">Past runs</h2>
                </header>
                <div className="card-body-flush">
                  <table className="table lab-runs">
                    <thead>
                      <tr>
                        <th>Strategy</th>
                        <th className="hide-sm">Window</th>
                        <th className="num">Return</th>
                        <th className="num">Sharpe</th>
                        <th className="num hide-sm">Max DD</th>
                        <th aria-label="Actions" />
                      </tr>
                    </thead>
                    <tbody>
                      {runs.data.runs.map((r) => (
                        <tr
                          key={r.id}
                          className={r.id === shownId ? 'lab-run-on' : ''}
                          onClick={() => setOpenId(r.id)}
                          tabIndex={0}
                          onKeyDown={(e) => e.key === 'Enter' && setOpenId(r.id)}
                        >
                          <td>{labels[r.strategy] ?? r.strategy}</td>
                          <td className="hide-sm text-dim mono">
                            {r.start.slice(0, 7)} → {r.end.slice(0, 7)}
                          </td>
                          <td className={'num ' + tone(r.total_return_pct)}>{pct(r.total_return_pct)}</td>
                          <td className="num">{r.sharpe?.toFixed(2) ?? '—'}</td>
                          <td className="num hide-sm negative">{pct(r.max_drawdown_pct)}</td>
                          <td className="num">
                            <button
                              className="btn btn-ghost btn-icon btn-sm"
                              aria-label="Delete run"
                              onClick={(e) => {
                                e.stopPropagation()
                                void remove(r.id)
                              }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Field({ spec, value, onChange }: { spec: ParamSpec; value: ParamValue; onChange: (v: ParamValue) => void }) {
  if (spec.type === 'choice')
    return (
      <div className="lab-field">
        <span className="lab-field-label">{spec.label}</span>
        <div className="seg" role="radiogroup" aria-label={spec.label}>
          {spec.options!.map((o) => (
            <button
              key={String(o)}
              role="radio"
              aria-checked={value === o}
              className={'seg-btn' + (value === o ? ' seg-on' : '')}
              onClick={() => onChange(o)}
            >
              {o === 'both' ? 'Long & short' : o === 'long' ? 'Long only' : `${o}${spec.unit ? ' ' + spec.unit : ''}`}
            </button>
          ))}
        </div>
      </div>
    )
  if (spec.type === 'bool')
    return (
      <label className="lab-field lab-field-check">
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        <span>{spec.label}</span>
      </label>
    )
  const isPct = spec.type === 'percent'
  const shown = value == null ? 0 : isPct ? Number(value) * 100 : Number(value)
  return (
    <label className="lab-field">
      <span className="lab-field-label">
        {spec.label}
        {spec.help && <span className="lab-field-help"> · {spec.help}</span>}
      </span>
      <input
        className="input mono"
        type="number"
        min={isPct ? spec.min! * 100 : spec.min}
        max={isPct ? spec.max! * 100 : spec.max}
        step={isPct ? spec.step! * 100 : spec.step}
        value={Number(shown.toFixed(4))}
        onChange={(e) => onChange(isPct ? Number(e.target.value) / 100 : Number(e.target.value))}
      />
    </label>
  )
}

function Results({ run, label }: { run: Run; label: string }) {
  const r = run.result
  const v = verdict(r)
  const oos = r.out_of_sample
  const years = Object.entries(r.by_year)
  const [tradeFilter, setTradeFilter] = useState<'all' | 'win' | 'loss'>('all')
  const trades = run.trades
    .filter((t) => (tradeFilter === 'all' ? true : tradeFilter === 'win' ? t.pnl > 0 : t.pnl <= 0))
    .slice()
    .reverse()
  const maxAbs = Math.max(1, ...years.map(([, y]) => Math.abs(y.total_return_pct ?? 0)))

  return (
    <>
      <section className="card">
        <header className="card-head">
          <div>
            <h2 className="card-title">
              {label}
              {run.label ? ` — ${run.label}` : ''}
            </h2>
            <p className="card-desc mono">
              {run.start} → {run.end} · {money(run.equity0)} start · {r.trades?.toLocaleString()} trades
            </p>
          </div>
        </header>
        <div className="card-body lab-result-body">
          <div className={`lab-verdict lab-verdict-${v.tone}`}>
            <strong>{v.title}</strong>
            <ul>
              {v.reasons.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>

          <div className="lab-stats">
            <Stat label="Total return" value={pct(r.total_return_pct)} cls={tone(r.total_return_pct)}
              foot={r.benchmark ? `SPY buy & hold ${pct(r.benchmark.total_return_pct)}` : undefined} />
            <Stat label="Per year" value={pct(r.cagr_pct)} cls={tone(r.cagr_pct)} />
            <Stat label="Sharpe" value={r.sharpe?.toFixed(2) ?? '—'}
              foot={r.benchmark ? `SPY ${r.benchmark.sharpe?.toFixed(2)}` : undefined} />
            <Stat label="Max drawdown" value={pct(r.max_drawdown_pct)} cls="negative"
              foot={r.benchmark ? `SPY ${pct(r.benchmark.max_drawdown_pct)}` : undefined} />
            <Stat label="Win rate" value={r.win_rate_pct != null ? `${r.win_rate_pct.toFixed(0)}%` : '—'}
              foot={r.avg_win != null ? `avg win ${money(r.avg_win)} · loss ${money(r.avg_loss ?? 0)}` : undefined} />
            <Stat label="Profit factor" value={r.profit_factor?.toFixed(2) ?? '—'}
              foot={r.worst_day_pct != null ? `worst day ${pct(r.worst_day_pct)}` : undefined} />
          </div>

          <EquityChart curve={run.equity_curve} />

          {oos && oos.days != null && oos.days > 0 && (
            <p className="lab-oos">
              <span className="badge badge-amber">Out of sample</span> Since {oos.from} — after the research was
              published — it returned <span className={tone(oos.total_return_pct)}>{pct(oos.total_return_pct)}</span> with
              Sharpe {oos.sharpe?.toFixed(2)} and a {pct(oos.max_drawdown_pct)} max drawdown. This is the number to trust.
            </p>
          )}
        </div>
      </section>

      <section className="card">
        <header className="card-head">
          <h2 className="card-title">By year</h2>
        </header>
        <div className="card-body lab-years">
          {years.map(([y, s]) => (
            <div key={y} className="lab-year">
              <span className="mono text-dim">{y}</span>
              <div className="lab-year-track">
                <span
                  className={'lab-year-bar ' + ((s.total_return_pct ?? 0) >= 0 ? 'lab-year-up' : 'lab-year-down')}
                  style={{ width: `${(Math.abs(s.total_return_pct ?? 0) / maxAbs) * 50}%` }}
                />
              </div>
              <span className={'mono num ' + tone(s.total_return_pct)}>{pct(s.total_return_pct)}</span>
              <span className="mono text-dim lab-year-sharpe hide-sm">Sharpe {s.sharpe?.toFixed(2) ?? '—'}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <header className="card-head">
          <div>
            <h2 className="card-title">Trades</h2>
            <p className="card-desc">
              {run.trades_total > run.trades.length
                ? `Latest ${run.trades.length} of ${run.trades_total.toLocaleString()}`
                : `${run.trades_total} trades`}
            </p>
          </div>
          <div className="seg" role="radiogroup" aria-label="Filter trades">
            {(['all', 'win', 'loss'] as const).map((f) => (
              <button key={f} role="radio" aria-checked={tradeFilter === f}
                className={'seg-btn' + (tradeFilter === f ? ' seg-on' : '')} onClick={() => setTradeFilter(f)}>
                {f === 'all' ? 'All' : f === 'win' ? 'Winners' : 'Losers'}
              </button>
            ))}
          </div>
        </header>
        <div className="card-body-flush lab-trades">
          <table className="table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Symbol</th>
                <th className="hide-sm">Side</th>
                <th className="hide-sm">Time</th>
                <th className="num hide-sm">Entry → exit</th>
                <th className="num">P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {trades.slice(0, 200).map((t, i) => (
                <tr key={`${t.day}-${t.symbol}-${t.entry_time}-${i}`}>
                  <td className="mono">{t.day}</td>
                  <td className="mono">{t.symbol}</td>
                  <td className="hide-sm">
                    <span className={'badge ' + (t.side === 'long' ? 'badge-green' : 'badge-red')}>{t.side}</span>
                  </td>
                  <td className="mono text-dim hide-sm">
                    {t.entry_time}–{t.exit_time} <span className="lab-reason">{t.reason}</span>
                  </td>
                  <td className="num mono hide-sm">
                    {t.entry.toFixed(2)} → {t.exit.toFixed(2)}
                  </td>
                  <td className={'num mono ' + tone(t.pnl)}>{money(t.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

function Stat({ label, value, foot, cls }: { label: string; value: string; foot?: string; cls?: string }) {
  return (
    <div className="lab-stat">
      <span className="stat-label">{label}</span>
      <span className={'stat-value ' + (cls ?? '')}>{value}</span>
      {foot && <span className="stat-foot">{foot}</span>}
    </div>
  )
}

function EquityChart({ curve }: { curve: [string, number][] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [theme] = useTheme()

  useEffect(() => {
    const el = ref.current
    if (!el || curve.length < 2) return
    const c = chartColors()
    const chart = createChart(el, {
      height: 260,
      layout: { background: { color: 'transparent' }, textColor: c.text, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: c.grid } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      localization: {
        priceFormatter: (p: number) => (p >= 10000 ? `$${(p / 1000).toFixed(p >= 100000 ? 0 : 1)}k` : `$${Math.round(p)}`),
      },
      handleScroll: false,
      handleScale: false,
    })
    const up = curve[curve.length - 1][1] >= curve[0][1]
    const line = up ? c.up : c.down
    const series = chart.addSeries(AreaSeries, {
      lineColor: line,
      lineWidth: 2,
      topColor: withAlpha(line, 0.16),
      bottomColor: withAlpha(line, 0),
      priceLineVisible: false,
    })
    const seen = new Set<number>()
    const toTs = (d: string) => (Date.parse(d + 'T16:00:00Z') / 1000) as UTCTimestamp
    series.setData(
      curve
        .map(([d, v]) => ({ time: toTs(d), value: v }))
        .filter((p) => (seen.has(p.time) ? false : (seen.add(p.time), true))),
    )
    // Starting equity as a dashed reference line.
    series.createPriceLine({ price: curve[0][1], color: c.grid, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: false })
    chart.timeScale().fitContent()
    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }))
    ro.observe(el)
    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [curve, theme])

  return <div className="lab-chart" ref={ref} />
}
