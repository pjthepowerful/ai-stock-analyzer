import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { SignalCard } from '../../components/SignalCard'
import type { StoredMessage } from '../../lib/chats'
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

  if (role === 'user') {
    return (
      <div className="msg msg-user">
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
        {meta?.taste && (
          <div className="msg-upsell">
            <span>Entry, stop, target, chart and reasoning are part of Paula Plus.</span>
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
        <CopyButton text={content} />
      </div>
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
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
    </div>
  )
}
