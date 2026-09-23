import { useChrome } from '../../lib/chrome'

interface Props {
  role: 'user' | 'assistant'
  content: string
  meta?: { taste?: boolean; limitReached?: boolean }
}

// Escapes HTML, then adds back a small set of safe formatting (bold, inline
// code, highlighted numbers) — same escape-first-then-format order as the
// original app's formatter, so this can never render attacker-controlled tags.
function formatMessage(text: string): string {
  let s = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/\$(\d[\d,]*\.?\d*)/g, '<span class="mono num-hl">$$$1</span>')
  s = s.replace(/\n/g, '<br/>')
  return s
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
