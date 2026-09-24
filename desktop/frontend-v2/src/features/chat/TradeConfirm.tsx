import { Check, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { api, ApiError, type TradeIntent } from '../../lib/api'
import type { StoredMessage } from '../../lib/chats'

type Meta = NonNullable<StoredMessage['meta']>

/** Plain-English summary of an order, used for the card and the stored
 *  message text (which the original app shows as-is). */
export function describeTrade(t: TradeIntent): string {
  const n = t.qty ? `${t.qty} share${t.qty === 1 ? '' : 's'} of ` : t.notional ? `$${t.notional} of ` : ''
  switch (t.action) {
    case 'buy':
      return t.smart ? `Buy ${n}${t.ticker}, sized to your risk` : `Buy ${n}${t.ticker}`
    case 'sell':
      return t.sell_all ? `Sell your whole ${t.ticker} position` : `Sell ${n}${t.ticker}`
    case 'short':
      return `Short ${n || '1 share of '}${t.ticker}`
    case 'cover':
      return t.cover_all ? `Cover your whole ${t.ticker} short` : `Cover ${n}${t.ticker}`
    case 'cancel_orders':
      return 'Cancel all open orders (this also removes protective stops)'
    case 'close_all':
      return 'Close every open position'
  }
}

interface Props {
  trade: TradeIntent
  state: Meta['tradeState']
  result?: string
  onChange: (meta: Meta) => void
}

export function TradeConfirm({ trade, state = 'pending', result, onChange }: Props) {
  const qc = useQueryClient()
  const danger = trade.action === 'close_all' || trade.action === 'cancel_orders'

  async function confirm() {
    onChange({ tradeState: 'placing' })
    try {
      const res = await api.post<{ ok: boolean; message?: string; error?: string }>('/api/trade/execute', trade)
      onChange(
        res.ok
          ? { tradeState: 'done', tradeResult: res.message ?? 'Order submitted' }
          : { tradeState: 'failed', tradeResult: res.error ?? 'Order failed' },
      )
      if (res.ok) {
        void qc.invalidateQueries({ queryKey: ['account'] })
        void qc.invalidateQueries({ queryKey: ['positions'] })
      }
    } catch (e) {
      onChange({ tradeState: 'failed', tradeResult: e instanceof ApiError ? e.message : 'Could not reach Paula.' })
    }
  }

  return (
    <div className={'trade-card' + (danger ? ' trade-card-danger' : '')}>
      <div className="trade-card-head">
        <span className="trade-card-label">
          {state === 'done'
            ? 'Order placed'
            : state === 'failed'
              ? 'Order not placed'
              : state === 'cancelled'
                ? 'Order cancelled'
                : 'Order — needs your confirmation'}
        </span>
        <strong className="trade-card-what">{describeTrade(trade)}</strong>
      </div>
      {state === 'pending' || state === 'placing' ? (
        <div className="trade-card-actions">
          <button className={'btn btn-sm ' + (danger ? 'btn-danger' : 'btn-primary')} onClick={confirm} disabled={state === 'placing'}>
            <Check size={13} />
            {state === 'placing' ? 'Placing…' : 'Confirm'}
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => onChange({ tradeState: 'cancelled' })} disabled={state === 'placing'}>
            <X size={13} />
            Cancel
          </button>
        </div>
      ) : (
        <p className={'trade-card-result trade-card-' + state}>
          {state === 'cancelled' ? 'Cancelled — nothing was sent to your broker.' : result}
        </p>
      )}
    </div>
  )
}
