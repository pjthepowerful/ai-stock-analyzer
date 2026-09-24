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
      <div className="msg msg-user">
        <p className="msg-user-text">{content}</p>
      </div>
    )
  }

  return (
    <div className="msg msg-assistant">
      <span className="msg-avatar">P</span>
      <div className="msg-assistant-body">
        <div className="msg-assistant-text" dangerouslySetInnerHTML={{ __html: formatMessage(content) }} />
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
      </div>
    </div>
  )
}
