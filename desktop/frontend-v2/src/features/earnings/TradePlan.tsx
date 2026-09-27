export interface Plan {
  available: boolean
  side: 'long' | 'short'
  note?: string
  entry?: number
  stop?: number
  stop_pct?: number
  targets?: number[]
  target_r?: number[]
  risk_per_share?: number
  atr?: number
  basis?: string
  resistance?: number
  shares?: number
  risk_dollars?: number
  size_note?: string
  earnings_move_pct?: number
  earnings_move_max_pct?: number
  earnings_quarters?: number
  warning?: string
}

const usd = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const pct = (from: number, to: number) => {
  const p = ((to - from) / from) * 100
  return `${p > 0 ? '+' : ''}${p.toFixed(1)}%`
}

/** One line for a table cell: stop and first target. */
export function TradePlanInline({ plan }: { plan?: Plan }) {
  if (!plan?.available || plan.entry == null || plan.stop == null || !plan.targets) return null
  return (
    <span className="plan-inline" title={plan.warning ?? plan.basis}>
      {plan.side === 'short' && <span className="plan-side">Short</span>}
      <span>
        Stop <b className="plan-neg">{usd(plan.stop)}</b>
      </span>
      <span>
        Target <b className="plan-pos">{usd(plan.targets[0])}</b>
      </span>
      {plan.earnings_move_pct != null && plan.stop_pct != null && plan.earnings_move_pct > plan.stop_pct && (
        <span className="plan-gap">gaps ±{plan.earnings_move_pct}%</span>
      )}
    </span>
  )
}

/**
 * Entry / stop / targets, with a risk-to-reward bar laid out like a
 * charting platform's position tool: red from stop to entry, green from
 * entry to the last target.
 */
export function TradePlan({ plan }: { plan?: Plan }) {
  if (!plan) return null
  if (!plan.available || plan.entry == null || plan.stop == null || !plan.targets) {
    return plan.note ? <p className="plan-note">No levels — {plan.note}</p> : null
  }
  const { entry, stop, targets } = plan
  const rs = plan.target_r ?? [2, 3]
  const risk = Math.abs(entry - stop)
  const reward = Math.abs(targets[targets.length - 1] - entry)
  const riskShare = (risk / (risk + reward)) * 100

  return (
    <div className="plan">
      <div className="plan-grid">
        <Level label={plan.side === 'short' ? 'Short entry' : 'Entry'} value={usd(entry)} sub="last close" />
        <Level label="Stop loss" value={usd(stop)} sub={pct(entry, stop)} tone="neg" />
        {targets.map((t, i) => (
          <Level key={i} label={`Target ${i + 1}`} value={usd(t)} sub={`${pct(entry, t)} · ${rs[i]}R`} tone="pos" />
        ))}
      </div>
      <div className="plan-bar" aria-hidden>
        <span className="plan-bar-risk" style={{ width: `${riskShare}%` }} />
        <span className="plan-bar-reward" />
      </div>
      <p className="plan-meta">
        Stop is {plan.basis}.
        {plan.resistance != null &&
          ` ${plan.side === 'short' ? 'Support' : 'Resistance'} at ${usd(plan.resistance)} (60-day ${plan.side === 'short' ? 'low' : 'high'}) comes before target 1.`}
        {plan.shares != null && plan.shares > 0 && ` ~${plan.shares} sh risks ${usd(plan.risk_dollars ?? 0)} (${plan.size_note}).`}
      </p>
      {plan.warning ? (
        <p className="plan-warn">{plan.warning}</p>
      ) : (
        plan.earnings_move_pct != null && (
          <p className="plan-meta">
            Typical earnings move ±{plan.earnings_move_pct}% (largest {plan.earnings_move_max_pct}% over {plan.earnings_quarters}{' '}
            quarters).
          </p>
        )
      )}
    </div>
  )
}

function Level({ label, value, sub, tone }: { label: string; value: string; sub: string; tone?: 'pos' | 'neg' }) {
  return (
    <div className="plan-level">
      <span className="plan-label">{label}</span>
      <span className={'plan-value' + (tone ? ` plan-${tone}` : '')}>{value}</span>
      <span className="plan-sub">{sub}</span>
    </div>
  )
}
