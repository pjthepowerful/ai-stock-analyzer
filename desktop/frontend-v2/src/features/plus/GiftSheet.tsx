import { Infinity as InfinityIcon, LineChart, MessageSquareQuote } from 'lucide-react'
import { useState } from 'react'
import { Sheet } from '../../components/Sheet'
import { ThankYou } from '../../components/ThankYou'
import { useSession } from '../../lib/auth'
import { useWebSocket } from '../../lib/ws'

// Same key the original app uses, so a note seen in either app counts.
const SEEN_KEY = 'paula-gift-seen'

function seen(msg: string) {
  try {
    return localStorage.getItem(SEEN_KEY) === msg
  } catch {
    return false
  }
}

/** When the team gifts Plus with a note, show it once. Arrives live if the
 *  person has Paula open, otherwise the next time they do. */
export function GiftSheet() {
  const { user, refresh } = useSession()
  const [closedFor, setClosedFor] = useState<string | null>(null)

  useWebSocket((e) => {
    if (e.event === 'plus_changed' && user && e.data.user_id === user.id) void refresh()
  })

  const msg = user?.plus ? (user.gift_msg ?? '').trim() : ''
  const open = !!msg && closedFor !== msg && !seen(msg)

  function close() {
    try {
      localStorage.setItem(SEEN_KEY, msg)
    } catch {
      /* ignore */
    }
    setClosedFor(msg)
  }

  if (!open) return null

  return (
    <Sheet open={open} onClose={close} title="">
      <ThankYou
        title="You’ve been gifted Paula Plus"
        subtitle={<span className="gift-note">“{msg}”</span>}
        rows={[
          { icon: InfinityIcon, title: 'Unlimited messages', desc: 'Ask Paula as much as you like, in as many chats as you want.' },
          { icon: LineChart, title: 'The full signal', desc: 'Entry, stop, target, chart and reasoning on every stock.' },
          { icon: MessageSquareQuote, title: 'Your own broker', desc: 'Connect your Alpaca paper account in Settings.' },
        ]}
        action={
          <button className="btn btn-primary" onClick={close}>
            Thank you
          </button>
        }
      />
    </Sheet>
  )
}
