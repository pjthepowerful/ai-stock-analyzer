import { useEffect, useState } from 'react'
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

interface Benchmark {
  ok: boolean
  portfolio_return_pct: number
  spy_return_pct: number | null
  alpha_pct: number | null
  beating_market: boolean
}

export function PortfolioScreen() {
  const [account, setAccount] = useState<Account | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<{ ok: boolean; data: Account }>('/api/account')
      .then((r) => setAccount(r.data))
      .catch(() => setError('Could not reach your brokerage account.'))
    api
      .get<{ ok: boolean; data: Position[] }>('/api/positions')
      .then((r) => setPositions(r.data))
      .catch(() => {})
    api
      .get<Benchmark>('/api/portfolio/benchmark')
      .then(setBenchmark)
      .catch(() => {})
  }, [])

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
