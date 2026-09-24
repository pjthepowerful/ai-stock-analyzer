import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { useChrome } from '../../lib/chrome'

interface Mover {
  ticker: string
  chg: number
  price: number
}

interface Overview {
  regime: string | null
  safe_to_buy: boolean | null
  reason: string | null
  spy: { price: number | null; pct: number | null }
  vix: { level: number; change: number; status: string } | null
  top_gainer: Mover | null
  top_loser: Mover | null
  tape: { sym: string; price: number; pct: number }[]
}

function pct(n: number) {
  return `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(2)}%`
}

function tone(n: number) {
  return n > 0 ? 'positive' : n < 0 ? 'negative' : ''
}

export function MarketStrip() {
  const { analyze } = useChrome()
  const q = useQuery({
    queryKey: ['market-overview'],
    queryFn: () => api.get<Overview>('/api/market/overview'),
    refetchInterval: 60_000,
    staleTime: 55_000,
  })

  // Quietly absent rather than a broken bar: this is ambient context.
  if (!q.data) return <div className="mstrip mstrip-empty" aria-hidden />

  const d = q.data
  return (
    <div className="mstrip" title={d.reason ?? undefined}>
      {d.regime && (
        <span className={'mstrip-regime mstrip-regime-' + d.regime}>
          {d.regime} market{d.safe_to_buy === false && ' · risk-off'}
        </span>
      )}
      {d.vix && (
        <span className="mstrip-item">
          <span className="mstrip-sym">VIX</span>
          <span className="mono">{d.vix.level.toFixed(1)}</span>
        </span>
      )}
      <div className="mstrip-tape">
        {d.tape.map((t) => (
          <button key={t.sym} className="mstrip-item" onClick={() => analyze(t.sym)} title={`Analyze ${t.sym}`}>
            <span className="mstrip-sym">{t.sym}</span>
            <span className={'mono ' + tone(t.pct)}>{pct(t.pct)}</span>
          </button>
        ))}
        {d.top_gainer && (
          <span className="mstrip-item">
            <span className="mstrip-sym">▲ {d.top_gainer.ticker}</span>
            <span className="mono positive">{pct(d.top_gainer.chg)}</span>
          </span>
        )}
        {d.top_loser && (
          <span className="mstrip-item">
            <span className="mstrip-sym">▼ {d.top_loser.ticker}</span>
            <span className="mono negative">{pct(d.top_loser.chg)}</span>
          </span>
        )}
      </div>
    </div>
  )
}
