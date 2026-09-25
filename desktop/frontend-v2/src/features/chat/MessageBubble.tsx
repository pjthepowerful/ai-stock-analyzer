import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { Chart } from '../../components/Chart'
import { SignalCard } from '../../components/SignalCard'
import type { StoredMessage } from '../../lib/chats'
import { useSession } from '../../lib/auth'
import { useChrome } from '../../lib/chrome'
import { formatMessage } from '../../lib/format'
import { TradeConfirm } from './TradeConfirm'

interface Props {
  role: 'user' | 'assistant'
  content: string
  meta?: StoredMessage['meta']
  onMeta?: (meta: StoredMessage['meta']) => void
}

export function MessageBubble({ role, content, meta, onMeta }: Props) {
  const { openPlus } = useChrome()
  const { user } = useSession()

  if (role === 'user') {
    return (
      <div className="msg msg-user">
        {meta?.image && <img className="msg-user-image" src={meta.image} alt="Attached image" />}
        <p className="msg-user-text">{content}</p>
      </div>
    )
  }

  return (
    <div className="msg msg-assistant">
      <span className="msg-avatar">P</span>
      <div className="msg-assistant-body">
        {meta?.trade ? (
          <TradeConfirm
            trade={meta.trade}
            state={meta.tradeState}
            result={meta.tradeResult}
            onChange={(m) => onMeta?.(m)}
          />
        ) : (
          <div className="msg-assistant-text" dangerouslySetInnerHTML={{ __html: formatMessage(content) }} />
        )}
        {meta?.card && (
          <div className="msg-card">
            <SignalCard data={meta.card} />
          </div>
        )}
        {meta?.charts && meta.charts.length > 0 && <ChatCharts tickers={meta.charts} />}
        {meta?.taste && (
          <div className="msg-upsell">
            <span>Entry, stop, target, chart and reasoning are part of Paula Plus.</span>
            <button className="btn btn-secondary btn-sm" onClick={openPlus}>
              See Plus
            </button>
          </div>
        )}
        {meta?.scanUpsell && !user?.plus && (
          <div className="msg-upsell">
            <span>This scan covered the ~100 most-liquid stocks. Plus scans all ~1,000 for more setups.</span>
            <button className="btn btn-secondary btn-sm" onClick={openPlus}>
              See Plus
            </button>
          </div>
        )}
        {meta?.limitReached && (
          <div className="msg-upsell">
            <span>You’ve hit today’s free message limit.</span>
            <button className="btn btn-secondary btn-sm" onClick={openPlus}>
              Go unlimited
            </button>
          </div>
        )}
        <CopyButton text={content} model={meta?.model} />
      </div>
    </div>
  )
}

/** One chart under the reply; several analyzed stocks get a picker. */
function ChatCharts({ tickers }: { tickers: string[] }) {
  const [picked, setPicked] = useState(tickers[0])
  const current = tickers.includes(picked) ? picked : tickers[0]
  return (
    <div className="msg-chart">
      {tickers.length > 1 && (
        <div className="seg msg-chart-pick" role="tablist" aria-label="Chart">
          {tickers.map((t) => (
            <button
              key={t}
              className={'seg-btn' + (t === current ? ' seg-on' : '')}
              role="tab"
              aria-selected={t === current}
              onClick={() => setPicked(t)}
            >
              {t}
            </button>
          ))}
        </div>
      )}
      <Chart ticker={current} height={300} />
    </div>
  )
}

function CopyButton({ text, model }: { text: string; model?: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="msg-actions">
      <button
        className="msg-action"
        onClick={() => {
          navigator.clipboard
            ?.writeText(text.replace(/\*\*/g, ''))
            .then(() => {
              setCopied(true)
              setTimeout(() => setCopied(false), 1400)
            })
            .catch(() => {})
        }}
        aria-label={copied ? 'Copied' : 'Copy reply'}
      >
        {copied ? <Check size={13} /> : <Copy size={13} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      {model && <span className="msg-model">{model}</span>}
    </div>
  )
}
