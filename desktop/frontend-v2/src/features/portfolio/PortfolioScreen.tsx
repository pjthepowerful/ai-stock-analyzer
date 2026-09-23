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

  return (
    <div className="portfolio-screen">
      {error && <div className="portfolio-error">{error}</div>}

      {account && (
        <div className="portfolio-hero">
          <span className="portfolio-eq-label">Equity</span>
          <span className="portfolio-eq-value mono">${account.equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          <span className={'portfolio-eq-change mono ' + (account.daily_pnl >= 0 ? 'positive' : 'negative')}>
            {account.daily_pnl >= 0 ? '+' : ''}
            ${account.daily_pnl.toFixed(2)} ({account.daily_pnl_pct.toFixed(2)}%) today
          </span>
        </div>
      )}

      {benchmark?.ok && (
        <div className="portfolio-bench">
          <div className="portfolio-bench-item">
            <span className="portfolio-bench-label">You</span>
            <span className={'mono ' + (benchmark.portfolio_return_pct >= 0 ? 'positive' : 'negative')}>
              {benchmark.portfolio_return_pct >= 0 ? '+' : ''}
              {benchmark.portfolio_return_pct.toFixed(2)}%
            </span>
          </div>
          <div className="portfolio-bench-item">
            <span className="portfolio-bench-label">S&amp;P 500</span>
            <span className="mono">{benchmark.spy_return_pct != null ? `${benchmark.spy_return_pct.toFixed(2)}%` : '—'}</span>
          </div>
          <div className="portfolio-bench-item">
            <span className="portfolio-bench-label">Alpha</span>
            <span className={'mono ' + (benchmark.beating_market ? 'positive' : 'negative')}>
              {benchmark.alpha_pct != null ? `${benchmark.alpha_pct.toFixed(2)}%` : '—'}
            </span>
          </div>
        </div>
      )}

      {exposure?.headroom != null && (
        <p className={'portfolio-pdt' + (exposure.headroom < 1000 ? ' portfolio-pdt-tight' : '')}>
          <span className="mono">
            {exposure.headroom >= 0 ? '$' : '−$'}
            {Math.abs(exposure.headroom).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>{' '}
          {exposure.headroom >= 0 ? 'above' : 'below'} the ${exposure.floor.toLocaleString()} pattern-day-trader floor
          {exposure.headroom < 0 && ' — day trades are restricted'}
          {exposure.positions > 0 && ` · ${exposure.note}`}
        </p>
      )}

      <Performance />

      <h2 className="portfolio-section-title">Open positions</h2>
      {positions.length === 0 ? (
        <div className="portfolio-empty">No open positions.</div>
      ) : (
        <div className="portfolio-positions">
          {positions.map((p) => (
            <div className="portfolio-pos" key={p.ticker}>
              <span className="mono portfolio-pos-ticker">{p.ticker}</span>
              <span className="portfolio-pos-qty">
                {p.qty} sh · avg ${p.avg_entry.toFixed(2)}
              </span>
              <div className="portfolio-pos-spacer" />
              <span className={'mono ' + (p.unrealized_pnl >= 0 ? 'positive' : 'negative')}>
                {p.unrealized_pnl >= 0 ? '+' : ''}
                ${p.unrealized_pnl.toFixed(2)} ({p.unrealized_pnl_pct.toFixed(2)}%)
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
