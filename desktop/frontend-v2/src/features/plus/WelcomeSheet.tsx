import { CalendarDays, ChartCandlestick, Lightbulb } from 'lucide-react'
import { useState } from 'react'
import { Sheet } from '../../components/Sheet'
import { ThankYou } from '../../components/ThankYou'
import { useSession } from '../../lib/auth'

const KEY = 'paula-v2-welcome'

function pending() {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

/** Shown once, right after creating an account. */
export function WelcomeSheet() {
  const { user } = useSession()
  const [open, setOpen] = useState(pending)

  function close() {
    setOpen(false)
    try {
      localStorage.removeItem(KEY)
    } catch {
      /* ignore */
    }
  }

  if (!user || !open) return null
  const first = user.username.split(' ')[0]

  return (
    <Sheet open={open} onClose={close} title="">
      <ThankYou
        title={`Thanks for joining, ${first}`}
        subtitle="Your account is ready. Here’s a good place to start."
        rows={[
          { icon: Lightbulb, title: 'Ask “What should I buy?”', desc: 'Paula scans the market for setups that clear her bar.' },
          { icon: ChartCandlestick, title: 'Analyze any ticker', desc: 'Signal, levels, chart and earnings in one view.' },
          { icon: CalendarDays, title: 'Check the earnings calendar', desc: 'Who reports this week, and Paula’s read on each.' },
        ]}
        action={
          <button className="btn btn-primary" onClick={close}>
            Let’s go
          </button>
        }
      />
    </Sheet>
  )
}
