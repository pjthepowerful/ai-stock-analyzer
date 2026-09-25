/** Fundamentals from the analyze payload, laid out like a broker's
 *  "Key statistics" block: label over value, four to a row. */

export interface Fundamentals {
  price: number
  name?: string
  sector?: string | null
  industry?: string | null
  market_cap?: number | null
  pe_ratio?: number | null
  forward_pe?: number | null
  dividend_yield?: number | null // already a percent (0.32 = 0.32%)
  beta?: number | null
  profit_margin?: number | null // fraction
  revenue_growth?: number | null // fraction
  '52w_high'?: number | null
  '52w_low'?: number | null
  target_price?: number | null
  target_low?: number | null
  target_high?: number | null
  num_analysts?: number | null
  recommendation?: string | null
  technicals?: { avg_volume?: number | null } | null
}

const ok = (n: number | null | undefined): n is number => typeof n === 'number' && Number.isFinite(n)

function compact(n: number | null | undefined, prefix = ''): string {
  if (!ok(n)) return '—'
  const abs = Math.abs(n)
  for (const [div, s] of [
    [1e12, 'T'],
    [1e9, 'B'],
    [1e6, 'M'],
    [1e3, 'K'],
  ] as const) {
    if (abs >= div) return `${prefix}${(n / div).toFixed(2)}${s}`
  }
  return `${prefix}${n.toFixed(0)}`
}

const money = (n: number | null | undefined) =>
  ok(n) ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'
const num = (n: number | null | undefined, d = 2) => (ok(n) ? n.toFixed(d) : '—')
const pct = (n: number | null | undefined, fraction = true) =>
  ok(n) ? `${(fraction ? n * 100 : n).toFixed(fraction ? 1 : 2)}%` : '—'

const REC: Record<string, string> = {
  strong_buy: 'Strong buy',
  buy: 'Buy',
  hold: 'Hold',
  underperform: 'Underperform',
  sell: 'Sell',
  strong_sell: 'Strong sell',
}

export function KeyStats({ data }: { data: Fundamentals }) {
  const lo = data['52w_low']
  const hi = data['52w_high']
  const inRange = ok(lo) && ok(hi) && hi > lo
  const pos = inRange ? Math.min(1, Math.max(0, (data.price - lo) / (hi - lo))) : 0
  const upside = ok(data.target_price) && data.price ? (data.target_price / data.price - 1) * 100 : null

  const stats: [string, string][] = [
    ['Market cap', compact(data.market_cap, '$')],
    ['P/E ratio', num(data.pe_ratio)],
    ['Forward P/E', num(data.forward_pe)],
    ['Dividend yield', ok(data.dividend_yield) && data.dividend_yield > 0 ? pct(data.dividend_yield, false) : '—'],
    ['Average volume', compact(data.technicals?.avg_volume)],
    ['Beta', num(data.beta)],
    ['Profit margin', pct(data.profit_margin)],
    ['Revenue growth', ok(data.revenue_growth) ? `${data.revenue_growth >= 0 ? '+' : ''}${pct(data.revenue_growth)}` : '—'],
  ]

  const hasAnything = stats.some(([, v]) => v !== '—') || inRange || ok(data.target_price)
  if (!hasAnything) return null

  return (
    <section className="card keystats">
      <header className="card-head">
        <h2 className="card-title">Key statistics</h2>
        {(data.sector || data.industry) && (
          <span className="keystats-sector">{[data.sector, data.industry].filter(Boolean).join(' · ')}</span>
        )}
      </header>
      <div className="card-body">
        <dl className="keystats-grid">
          {stats.map(([label, value]) => (
            <div key={label} className="keystats-cell">
              <dt>{label}</dt>
              <dd className="mono">{value}</dd>
            </div>
          ))}
        </dl>

        <div className="keystats-bands">
          {inRange && (
            <div className="keystats-band">
              <div className="keystats-band-head">
                <span>52-week range</span>
                <span className="text-dim">{Math.round(pos * 100)}% of the way up</span>
              </div>
              <div className="keystats-track" aria-hidden>
                <span className="keystats-marker" style={{ left: `${pos * 100}%` }} />
              </div>
              <div className="keystats-band-ends mono">
                <span>{money(lo)}</span>
                <span>{money(hi)}</span>
              </div>
            </div>
          )}

          {ok(data.target_price) && (
            <div className="keystats-band">
              <div className="keystats-band-head">
                <span>
                  Analyst target{' '}
                  <strong className="mono">{money(data.target_price)}</strong>
                  {upside != null && (
                    <span className={'mono ' + (upside >= 0 ? 'positive' : 'negative')}>
                      {' '}
                      ({upside >= 0 ? '+' : '−'}
                      {Math.abs(upside).toFixed(1)}%)
                    </span>
                  )}
                </span>
                <span className="text-dim">
                  {data.recommendation ? (REC[data.recommendation] ?? data.recommendation) : ''}
                  {data.num_analysts ? ` · ${data.num_analysts} analysts` : ''}
                </span>
              </div>
              {ok(data.target_low) && ok(data.target_high) && data.target_high > data.target_low && (
                <>
                  <div className="keystats-track" aria-hidden>
                    <span
                      className="keystats-marker keystats-marker-now"
                      title="Current price"
                      style={{
                        left: `${Math.min(1, Math.max(0, (data.price - data.target_low) / (data.target_high - data.target_low))) * 100}%`,
                      }}
                    />
                    <span
                      className="keystats-marker keystats-marker-target"
                      title="Average target"
                      style={{
                        left: `${Math.min(1, Math.max(0, (data.target_price - data.target_low) / (data.target_high - data.target_low))) * 100}%`,
                      }}
                    />
                  </div>
                  <div className="keystats-band-ends mono">
                    <span>Low {money(data.target_low)}</span>
                    <span>High {money(data.target_high)}</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
