import { SignalCard } from '../../components/SignalCard'
import type { StoredMessage } from '../../lib/chats'
import { useChrome } from '../../lib/chrome'
import { formatMessage } from '../../lib/format'

interface Props {
  role: 'user' | 'assistant'
  content: string
  meta?: StoredMessage['meta']
}

export function MessageBubble({ role, content, meta }: Props) {
  const { openPlus } = useChrome()
  if (role === 'user') {
    return (
      <div className="msg-row msg-row-user">
        <p className="msg-user-text">{content}</p>
      </div>
    )
  }

  return (
    <div className="msg-row msg-row-assistant">
      <div className="msg-assistant-text" dangerouslySetInnerHTML={{ __html: formatMessage(content) }} />
      {meta?.card && (
        <div className="msg-card">
          <SignalCard data={meta.card} />
        </div>
      )}
      {meta?.taste && (
        <div className="msg-upsell">
          Full breakdown — entry/stop/target, chart, reasoning — is part of Paula Plus.{' '}
          <button className="msg-upsell-btn" onClick={openPlus}>
            See Plus →
          </button>
        </div>
      )}
      {meta?.limitReached && (
        <div className="msg-upsell">
          You've hit today's free message limit.{' '}
          <button className="msg-upsell-btn" onClick={openPlus}>
            Go unlimited →
          </button>
        </div>
      )}
    </div>
  )
}
