import { Check, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import './SignalCard.css'

export interface TradeLevels {
  entry: number
  stop_loss: number
  target_1: number
  target_2?: number
  risk_reward: number
  risk_pct: number
}

export interface Signal {
  action: string
  score: number
  confidence: number
  setup: string
  category_scores: Record<string, number>
  signals: string[]
  warnings: string[]
  trade?: TradeLevels
  /** Buyer's levels for every rating: stop below entry, targets above. */
  plan?: TradeLevels
}

export interface AnalyzeData {
  ticker: string
  name?: string
  price: number
  change: number
  change_pct: number
  signal: Signal
}

const CATEGORY_LABELS: Record<string, string> = {
  trend: 'Trend',
  pullback: 'Pullback',
  momentum: 'Momentum',
  volume: 'Volume',
  rsi: 'RSI',
  news: 'News',
}

function actionClass(action: string): string {
  if (action.includes('BUY')) return 'badge-green'
  if (action.includes('SELL')) return 'badge-red'
  return ''
}

/** Levels shown to the reader are always the buyer's: stop below entry,
 *  target above. `trade` can be short-side on a sell rating (the autopilot
 *  shorts with it), which reads as "stop above target" to anyone buying. */
function buyerLevels(signal: Signal): TradeLevels | undefined {
  const t = signal.plan ?? signal.trade
  if (!t || !(t.entry > 0)) return undefined
  if (t.stop_loss >= t.entry || t.target_1 <= t.entry) return undefined
  return t
}

function levelsCaption(action: string): string {
  if (action.includes('BUY')) return 'Long setup · stop below entry, target above'
  if (action.includes('SELL'))
    return 'Sell signal, not a buy. If you hold it, the stop is where to get out; the target is what a recovery would need.'
  return 'No trade signal · levels only if you buy anyway'
}

export function SignalCard({ data }: { data: AnalyzeData }) {
  const { signal } = data
  const levels = buyerLevels(signal)
  const up = data.change >= 0
  const factors = Object.entries(signal.category_scores)
  // Factor scores are small signed integers; scale bars to the largest so
  // they're readable, growing left (bearish) or right (bullish) of center.
  const maxAbs = Math.max(1, ...factors.map(([, v]) => Math.abs(v)))
  // On phones the reasons fold to the top few (warnings always show) so the
  // levels and chart aren't two screens down — Robinhood's "Show more".
  const [allNotes, setAllNotes] = useState(false)
  const FOLD = 3
  const hidden = Math.max(0, signal.signals.length - FOLD)

  return (
    <div className="signal-card card">
      <div className="sig-head">
        <div className="sig-id">
          <span className="sig-ticker">{data.ticker}</span>
          {data.name && <span className="sig-name">{data.name}</span>}
        </div>
        <div className="sig-quote">
          <span className="sig-price">${data.price.toFixed(2)}</span>
          <span className={'sig-change ' + (up ? 'positive' : 'negative')}>
            {up ? '+' : '−'}
            {Math.abs(data.change).toFixed(2)} ({up ? '+' : '−'}
            {Math.abs(data.change_pct).toFixed(2)}%)
          </span>
        </div>
      </div>

      <div className="sig-verdict">
        <span className={'badge ' + actionClass(signal.action)}>{signal.action.replace('_', ' ')}</span>
        <span className="sig-setup">{signal.setup}</span>
      </div>

      <div className="sig-metrics">
        <div>
          <span className="sig-metric-label">Score</span>
          <span className="sig-metric-value">
            {signal.score}
            <small>/100</small>
          </span>
        </div>
        <div>
          <span className="sig-metric-label">Confidence</span>
          <span className="sig-metric-value">
            {signal.confidence}
            <small>%</small>
          </span>
        </div>
      </div>

      <div className="sig-bars">
        {factors.map(([key, value]) => (
          <div className="sig-bar-row" key={key}>
            <span className="sig-bar-label">{CATEGORY_LABELS[key] ?? key}</span>
            <div className="sig-bar-track">
              <div
                className={'sig-bar-fill ' + (value >= 0 ? 'sig-bar-pos' : 'sig-bar-neg')}
                style={{ width: `${(Math.abs(value) / maxAbs) * 50}%` }}
              />
            </div>
            <span className="sig-bar-value">{value > 0 ? `+${value}` : value}</span>
          </div>
        ))}
      </div>

      {(signal.signals.length > 0 || signal.warnings.length > 0) && (
        <ul className={'sig-notes' + (allNotes ? ' sig-notes-all' : '')}>
          {signal.signals.map((s, i) => (
            <li className={'sig-note sig-note-good' + (i >= FOLD ? ' sig-note-extra' : '')} key={s}>
              <Check size={14} strokeWidth={2.2} />
              {s}
            </li>
          ))}
          {signal.warnings.map((w) => (
            <li className="sig-note sig-note-warn" key={w}>
              <TriangleAlert size={14} strokeWidth={2} />
              {w}
            </li>
          ))}
          {hidden > 0 && !allNotes && (
            <li className="sig-note-more">
              <button type="button" onClick={() => setAllNotes(true)}>
                Show {hidden} more reason{hidden === 1 ? '' : 's'}
              </button>
            </li>
          )}
        </ul>
      )}

      {levels && (
        <>
          <p className="sig-trade-side">{levelsCaption(signal.action)}</p>
          <dl className="sig-trade">
            <div>
              <dt>Entry</dt>
              <dd>${levels.entry.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Stop loss</dt>
              <dd className="negative">${levels.stop_loss.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Profit target</dt>
              <dd className="positive">${levels.target_1.toFixed(2)}</dd>
            </div>
            <div>
              <dt>R:R</dt>
              <dd>{levels.risk_reward.toFixed(1)}:1</dd>
            </div>
          </dl>
        </>
      )}
    </div>
  )
}
