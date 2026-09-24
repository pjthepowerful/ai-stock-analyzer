import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { useSession } from '../../lib/auth'

interface Account {
  equity: number
  daily_pnl: number
  daily_pnl_pct: number
}

interface Overview {
  regime: string | null
  spy: { pct: number | null }
  tape: { sym: string; pct: number }[]
}

/** Four at-a-glance numbers under the greeting (signed-in only). Shares query
 *  keys with Portfolio and the market strip, so it's usually instant. */
export function Snapshot() {
  const { user } = useSession()
  const enabled = !!user
  const account = useQuery({
    queryKey: ['account'],
    queryFn: () => api.get<{ data: Account }>('/api/account').then((r) => r.data),
    enabled,
  })
  const positions = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.get<{ data: unknown[] }>('/api/positions').then((r) => r.data),
    enabled,
  })
  const market = useQuery({
    queryKey: ['market-overview'],
    queryFn: () => api.get<Overview>('/api/market/overview'),
    staleTime: 55_000,
  })

  if (!enabled || !account.data) return null
  const a = account.data
  const up = a.daily_pnl >= 0
  // The regime check sometimes omits SPY's move; the tape always has it.
  const spy = market.data?.spy.pct ?? market.data?.tape.find((t) => t.sym === 'SPY')?.pct ?? null

  return (
    <div className="snap">
      <div className="snap-cell">
        <span className="snap-label">Equity</span>
        <span className="snap-value">${a.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
      </div>
      <div className="snap-cell">
        <span className="snap-label">Today</span>
        <span className={'snap-value ' + (a.daily_pnl === 0 ? '' : up ? 'positive' : 'negative')}>
          {Math.round(a.daily_pnl) === 0 ? '$0' : `${up ? '+' : '−'}$${Math.abs(a.daily_pnl).toFixed(0)}`}
        </span>
      </div>
      <div className="snap-cell">
        <span className="snap-label">Market</span>
        <span className={'snap-value ' + (spy == null ? '' : spy >= 0 ? 'positive' : 'negative')}>
          {spy == null ? '—' : `SPY ${spy >= 0 ? '+' : '−'}${Math.abs(spy).toFixed(2)}%`}
        </span>
      </div>
      <div className="snap-cell">
        <span className="snap-label">Positions</span>
        <span className="snap-value">{positions.data?.length ?? '—'}</span>
      </div>
    </div>
  )
}
