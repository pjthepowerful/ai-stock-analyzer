import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../lib/api'

interface Decile {
  decile?: number
  n: number
  score_min: number
  score_max: number
  mean_fwd_ret_pct: number
  hit_rate_pct: number
}

interface SignalResult {
  generated_at: string
  universe_size: number
  n_observations: number
  horizon: number
  years: number
  rank_ic: number
  top_minus_bottom_pct: number
  monotonic_up_steps: number
  verdict: 'SIGNAL' | 'MIXED' | 'NO EDGE' | 'INVERTED'
  detail: string
  deciles: Decile[]
  caveats: string
}

interface BacktestResult {
  generated_at?: string
  params?: { days: number; min_score: number }
  stats: {
    total_trades: number
    win_rate: number
    total_pnl_pct: number
    profit_factor: number
    max_drawdown: number
  }
  validation?: {
    ok: boolean
    error?: string
    verdict?: 'PASS' | 'FAIL' | 'INCONCLUSIVE'
    reasons?: string[]
    summary?: { trades: number; total_gross_pct: number; total_net_pct: number; cost_drag_pct: number }
    bootstrap?: { ok: boolean; mean_pct: number; ci_low_pct: number; ci_high_pct: number }
  }
}

interface Job<T> {
  status: 'idle' | 'running' | 'done' | 'error'
  error: string | null
  started_at: number | null
  result: T | null
}

interface StrategyStatus {
  signal: Job<SignalResult>
  backtest: Job<BacktestResult>
}

const TONE: Record<string, string> = {
  SIGNAL: 'positive',
  PASS: 'positive',
  MIXED: 'warn',
  INCONCLUSIVE: 'warn',
  'NO EDGE': 'negative',
  INVERTED: 'negative',
  FAIL: 'negative',
}

function pct(n: number | undefined, d = 2) {
  if (n == null) return '—'
  return `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(d)}%`
}

function since(ts: number | null) {
  if (!ts) return ''
  const m = Math.floor((Date.now() / 1000 - ts) / 60)
  return m < 1 ? 'under a minute' : `${m} min`
}

export function StrategyPanel() {
  const qc = useQueryClient()
  const q = useQuery({
    queryKey: ['admin', 'strategy'],
    queryFn: () => api.get<StrategyStatus>('/api/admin/strategy'),
    // Poll only while something is running.
    refetchInterval: (query) => {
      const d = query.state.data
      return d && (d.signal.status === 'running' || d.backtest.status === 'running') ? 5000 : false
    },
  })
  const run = useMutation({
    mutationFn: (kind: 'signal' | 'backtest') => api.post(`/api/admin/strategy/${kind}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'strategy'] }),
  })

  if (q.isPending) return <p className="admin-empty">Loading…</p>
  if (q.error) return <p className="admin-error">{q.error.message}</p>
  const { signal, backtest } = q.data

  return (
    <section className="strat">
      <p className="admin-dim">
        Two honest checks on the strategy. Both are read-only: they change no settings and place no orders.
      </p>

      <article className="card strat-block">
        <header className="strat-head">
          <div>
            <h3 className="strat-title">Does the score predict returns?</h3>
            <p className="strat-sub">
              Scores ~2 years of history and checks whether higher scores actually earn more over the next few days.
            </p>
          </div>
          <RunButton job={signal} onRun={() => run.mutate('signal')} busy={run.isPending} />
        </header>
        {signal.status === 'error' && <p className="admin-error">{signal.error}</p>}
        {signal.result ? <SignalView r={signal.result} /> : <p className="admin-empty">Not run yet.</p>}
      </article>

      <article className="card strat-block">
        <header className="strat-head">
          <div>
            <h3 className="strat-title">Does the strategy survive costs?</h3>
            <p className="strat-sub">
              Backtests the last year with current autopilot settings, then applies trading costs, a bootstrap
              confidence interval and a random-entry comparison.
            </p>
          </div>
          <RunButton job={backtest} onRun={() => run.mutate('backtest')} busy={run.isPending} />
        </header>
        {backtest.status === 'error' && <p className="admin-error">{backtest.error}</p>}
        {backtest.result ? <BacktestView r={backtest.result} /> : <p className="admin-empty">Not run yet.</p>}
      </article>
    </section>
  )
}

function RunButton({ job, onRun, busy }: { job: Job<unknown>; onRun: () => void; busy: boolean }) {
  if (job.status === 'running') {
    return <span className="strat-running mono">running · {since(job.started_at)}</span>
  }
  return (
    <button className="btn btn-primary btn-sm" onClick={onRun} disabled={busy}>
      {job.result ? 'Run again' : 'Run'}
    </button>
  )
}

function SignalView({ r }: { r: SignalResult }) {
  const max = Math.max(...r.deciles.map((d) => Math.abs(d.mean_fwd_ret_pct)), 0.001)
  return (
    <div className="strat-body">
      <p className="strat-verdict">
        <span className={'strat-badge ' + TONE[r.verdict]}>{r.verdict}</span>
        {r.detail}
      </p>
      <dl className="strat-stats">
        <div>
          <dt>Rank IC</dt>
          <dd className="mono">{r.rank_ic.toFixed(3)}</dd>
        </div>
        <div>
          <dt>Top − bottom decile</dt>
          <dd className="mono">{pct(r.top_minus_bottom_pct)}</dd>
        </div>
        <div>
          <dt>Rising steps</dt>
          <dd className="mono">{r.monotonic_up_steps}/9</dd>
        </div>
        <div>
          <dt>Observations</dt>
          <dd className="mono">{r.n_observations.toLocaleString()}</dd>
        </div>
      </dl>

      {/* Mean forward return per score decile — the picture of whether the
          score orders outcomes. A working score slopes up left to right. */}
      <div className="strat-deciles" role="img" aria-label="Mean forward return by score decile">
        {r.deciles.map((d, i) => {
          const h = (Math.abs(d.mean_fwd_ret_pct) / max) * 50
          const up = d.mean_fwd_ret_pct >= 0
          return (
            <div key={i} className="strat-decile" title={`Scores ${d.score_min}–${d.score_max}: ${pct(d.mean_fwd_ret_pct, 3)} over ${r.horizon}d, ${d.hit_rate_pct}% up`}>
              <div className="strat-decile-track">
                <div
                  className={'strat-decile-bar ' + (up ? 'strat-up' : 'strat-down')}
                  style={up ? { bottom: '50%', height: `${h}%` } : { top: '50%', height: `${h}%` }}
                />
              </div>
              <span className="strat-decile-label mono">{i + 1}</span>
            </div>
          )
        })}
      </div>
      <p className="strat-axis">
        Score decile (1 = lowest) · mean {r.horizon}-day forward return · generated{' '}
        {new Date(r.generated_at).toLocaleString()}
      </p>
      <p className="strat-caveat">{r.caveats}</p>
    </div>
  )
}

function BacktestView({ r }: { r: BacktestResult }) {
  const v = r.validation
  return (
    <div className="strat-body">
      {v?.ok && v.verdict ? (
        <div className="strat-verdict">
          <span className={'strat-badge ' + TONE[v.verdict]}>{v.verdict}</span>
          <ul className="strat-reasons">
            {(v.reasons ?? []).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>
      ) : (
        v?.error && <p className="admin-error">Validation: {v.error}</p>
      )}
      <dl className="strat-stats">
        <div>
          <dt>Trades</dt>
          <dd className="mono">{r.stats.total_trades}</dd>
        </div>
        <div>
          <dt>Win rate</dt>
          <dd className="mono">{r.stats.win_rate}%</dd>
        </div>
        <div>
          <dt>Account return</dt>
          <dd className="mono" title="Simulated dollar P&L as a share of starting capital">
            {pct(r.stats.total_pnl_pct)}
          </dd>
        </div>
        {v?.summary && (
          <div>
            <dt>Σ trade returns</dt>
            <dd
              className="mono"
              title={`Sum of per-trade % returns: ${pct(v.summary.total_gross_pct)} before costs, ${pct(v.summary.total_net_pct)} after`}
            >
              {pct(v.summary.total_net_pct)}
              <small className="strat-small"> net · −{Math.abs(v.summary.cost_drag_pct).toFixed(2)}% costs</small>
            </dd>
          </div>
        )}
        <div>
          <dt>Profit factor</dt>
          <dd className="mono">{r.stats.profit_factor}</dd>
        </div>
        <div>
          <dt>Max drawdown</dt>
          <dd className="mono">{r.stats.max_drawdown}%</dd>
        </div>
      </dl>
      {v?.bootstrap?.ok && (
        <p className="strat-axis">
          Per-trade mean {pct(v.bootstrap.mean_pct, 3)}, 95% interval {pct(v.bootstrap.ci_low_pct, 3)} to{' '}
          {pct(v.bootstrap.ci_high_pct, 3)}
        </p>
      )}
      {r.generated_at && (
        <p className="strat-axis">
          {r.params?.days}-day window, min score {r.params?.min_score} · generated{' '}
          {new Date(r.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  )
}
