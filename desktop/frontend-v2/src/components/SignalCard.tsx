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
  if (action.includes('BUY')) return 'sig-buy'
  if (action.includes('SELL')) return 'sig-sell'
  return 'sig-hold'
}

export function SignalCard({ data }: { data: AnalyzeData }) {
  const { signal } = data
  const up = data.change >= 0

  return (
    <div className="signal-card">
      <div className="sig-head">
        <span className="sig-ticker mono">{data.ticker}</span>
        {data.name && <span className="sig-name">{data.name}</span>}
        <div className="sig-spacer" />
        <span className={'mono ' + (up ? 'positive' : 'negative')}>
          ${data.price.toFixed(2)} {up ? '+' : ''}
          {data.change.toFixed(2)} ({data.change_pct.toFixed(2)}%)
        </span>
      </div>

      <div className="sig-verdict">
        <span className={'sig-action ' + actionClass(signal.action)}>{signal.action.replace('_', ' ')}</span>
        <span className="sig-score mono">
          score <b>{signal.score}</b>/100 · confidence <b>{signal.confidence}</b>%
        </span>
        <span className="sig-setup">{signal.setup}</span>
      </div>

      <div className="sig-bars">
        {Object.entries(signal.category_scores).map(([key, value]) => (
          <div className="sig-bar-row" key={key}>
            <span className="sig-bar-label">{CATEGORY_LABELS[key] ?? key}</span>
            <div className="sig-bar-track">
              <div
                className={'sig-bar-fill ' + (value >= 0 ? 'positive-bg' : 'negative-bg')}
                style={{ width: `${Math.min(100, Math.abs(value))}%` }}
              />
            </div>
            <span className="sig-bar-value mono">{value}</span>
          </div>
        ))}
      </div>

      {(signal.signals.length > 0 || signal.warnings.length > 0) && (
        <div className="sig-notes">
          {signal.signals.map((s) => (
            <div className="sig-note sig-note-good" key={s}>
              ✓ {s}
            </div>
          ))}
          {signal.warnings.map((w) => (
            <div className="sig-note sig-note-warn" key={w}>
              ⚠ {w}
            </div>
          ))}
        </div>
      )}

      {signal.trade && (
        <div className="sig-trade">
          <div className="sig-trade-row">
            <span>Entry</span>
            <span className="mono">${signal.trade.entry.toFixed(2)}</span>
          </div>
          <div className="sig-trade-row">
            <span>Stop</span>
            <span className="mono negative">${signal.trade.stop_loss.toFixed(2)}</span>
          </div>
          <div className="sig-trade-row">
            <span>Target</span>
            <span className="mono positive">${signal.trade.target_1.toFixed(2)}</span>
          </div>
          <div className="sig-trade-row">
            <span>Reward:risk</span>
            <span className="mono">{signal.trade.risk_reward.toFixed(1)}:1</span>
          </div>
        </div>
      )}
    </div>
  )
}
