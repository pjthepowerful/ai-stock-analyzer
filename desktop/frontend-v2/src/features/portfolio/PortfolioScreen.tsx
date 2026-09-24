import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { Performance } from './Performance'
import './portfolio.css'

interface Account {
  equity: number
  cash: number
  buying_power: number
  daily_pnl: number
  daily_pnl_pct: number
  status: string
}

interface Position {
  ticker: string
  qty: number
  side: string
  avg_entry: number
  current_price: number
  market_value: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  stop_loss: number
}

interface Exposure {
  equity: number | null
  floor: number
  headroom: number | null
  exposure: number
  positions: number
  note: string
}

interface Benchmark {
  ok: boolean
  portfolio_return_pct: number
  spy_return_pct: number | null
  alpha_pct: number | null
  beating_market: boolean
}

export function PortfolioScreen() {
  // Cached across tab switches (staleTime from the QueryClient defaults), so
  // coming back to Portfolio doesn't re-wait on four broker round trips.
  const accountQ = useQuery({
    queryKey: ['account'],
    queryFn: () => api.get<{ ok: boolean; data: Account }>('/api/account').then((r) => r.data),
  })
  const positionsQ = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.get<{ ok: boolean; data: Position[] }>('/api/positions').then((r) => r.data),
  })
  const benchmarkQ = useQuery({
    queryKey: ['benchmark'],
    queryFn: () => api.get<Benchmark>('/api/portfolio/benchmark'),
    retry: false,
  })
  const exposureQ = useQuery({
    queryKey: ['exposure'],
    queryFn: () => api.get<Exposure>('/api/research/exposure'),
    retry: false,
  })

  const account = accountQ.data ?? null
  const positions = positionsQ.data ?? []
  const benchmark = benchmarkQ.data ?? null
  const exposure = exposureQ.data ?? null
  const error = accountQ.error ? 'Could not reach your brokerage account.' : null

  const signedPct = (n: number) => `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(2)}%`
  const tone = (n: number) => (n > 0 ? 'positive' : n < 0 ? 'negative' : '')

  return (
    <div className="page">
      <div className="page-inner">
        <header className="page-head">
          <div>
            <h1 className="page-title">Portfolio</h1>
            <p className="page-sub">Your Alpaca paper account</p>
          </div>
        </header>

        {error && <p className="note-warn">{error}</p>}

        <div className="grid-stats">
          <div className="card stat">
            <span className="stat-label">Equity</span>
            <span className="stat-value">
              {account ? `$${account.equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—'}
            </span>
            {account && (
              <span className={'stat-foot ' + tone(account.daily_pnl)}>
                {account.daily_pnl >= 0 ? '+' : '−'}${Math.abs(account.daily_pnl).toFixed(2)} (
                {signedPct(account.daily_pnl_pct)}) today
              </span>
            )}
          </div>

          <div className="card stat">
            <span className="stat-label">Return this month</span>
            <span className={'stat-value ' + (benchmark ? tone(benchmark.portfolio_return_pct) : '')}>
              {benchmark ? signedPct(benchmark.portfolio_return_pct) : '—'}
            </span>
            {benchmark?.spy_return_pct != null && (
              <span className="stat-foot">S&amp;P 500 {signedPct(benchmark.spy_return_pct)}</span>
            )}
          </div>

          <div className="card stat">
            <span className="stat-label">Vs. the market</span>
            <span className={'stat-value ' + (benchmark?.alpha_pct != null ? tone(benchmark.alpha_pct) : '')}>
              {benchmark?.alpha_pct != null ? signedPct(benchmark.alpha_pct) : '—'}
            </span>
            {benchmark && (
              <span className="stat-foot">{benchmark.beating_market ? 'Ahead of the S&P' : 'Behind the S&P'}</span>
            )}
          </div>

          <div className="card stat">
            <span className="stat-label">Day-trade headroom</span>
            <span className={'stat-value ' + (exposure?.headroom != null && exposure.headroom < 1000 ? 'warn' : '')}>
              {exposure?.headroom != null
                ? `${exposure.headroom < 0 ? '−' : ''}$${Math.abs(exposure.headroom).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                : '—'}
            </span>
            {exposure && (
              <span className="stat-foot">
                {exposure.headroom != null && exposure.headroom < 0
                  ? 'Below the $25k PDT floor — day trades restricted'
                  : `Above the $${exposure.floor.toLocaleString()} PDT floor`}
              </span>
            )}
          </div>
        </div>

        <Performance />

        <section className="card">
          <header className="card-head">
            <div>
              <h2 className="card-title">Open positions</h2>
              <p className="card-desc">{positions.length ? `${positions.length} held` : 'Nothing held right now'}</p>
            </div>
          </header>
          <div className="card-body-flush">
            {positions.length === 0 ? (
              <p className="empty">No open positions.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th className="num">Shares</th>
                    <th className="num">Avg cost</th>
                    <th className="num">Price</th>
                    <th className="num">Market value</th>
                    <th className="num">Unrealized</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p) => (
                    <tr key={p.ticker}>
                      <td className="pos-sym">{p.ticker}</td>
                      <td className="num">{p.qty}</td>
                      <td className="num">${p.avg_entry.toFixed(2)}</td>
                      <td className="num">${p.current_price.toFixed(2)}</td>
                      <td className="num">${p.market_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                      <td className={'num ' + tone(p.unrealized_pnl)}>
                        {p.unrealized_pnl >= 0 ? '+' : '−'}${Math.abs(p.unrealized_pnl).toFixed(2)}
                        <span className="text-dim"> {signedPct(p.unrealized_pnl_pct)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
