import { useState } from 'react'
import { ChartCandlestick, MessagesSquare, Wallet } from 'lucide-react'
import { Sheet } from '../../components/Sheet'
import { ThankYou } from '../../components/ThankYou'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/auth'
import './plus.css'

type Plan = 'monthly' | 'annual'

const PLANS: Record<Plan, { label: string; price: string; per: string; note: string }> = {
  monthly: { label: 'Monthly', price: '$9.99', per: '/mo', note: 'Billed monthly' },
  annual: { label: 'Annual', price: '$99', per: '/yr', note: '$8.25/mo · two months free' },
}

const FEATURES: [string, string][] = [
  ['Unlimited messages', 'No daily cap on questions.'],
  ['The full signal', 'Entry, stop, target, chart and reasoning on every ticker — not just the verdict.'],
  ['Your own broker', 'Connect your Alpaca account; keys are encrypted at rest.'],
  ['Unlimited chats', 'A separate thread for every idea, synced across your devices.'],
]

interface Props {
  open: boolean
  onClose: () => void
}

export function PlusSheet({ open, onClose }: Props) {
  const { user, isGuest, refresh, signOut } = useSession()
  const [plan, setPlan] = useState<Plan>('annual')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [thanked, setThanked] = useState(false)

  function close() {
    onClose()
    setThanked(false)
  }

  async function buy() {
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/plus/purchase', { plan })
      await refresh()
      setThanked(true)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Checkout failed — nothing was charged.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet open={open} onClose={close} title={thanked ? '' : user?.plus ? 'You have Plus' : 'Paula Plus'}>
      {thanked ? (
        <ThankYou
          title="Thank you — you’re on Plus"
          subtitle={
            <>
              Your {PLANS[plan].label.toLowerCase()} plan is active{user?.username ? `, ${user.username.split(' ')[0]}` : ''}.
              Everything below is unlocked now.
            </>
          }
          rows={[
            { icon: MessagesSquare, title: 'Unlimited messages', desc: 'No daily cap — ask as much as you like.' },
            { icon: ChartCandlestick, title: 'The full signal', desc: 'Entry, stop, target and chart on every ticker.' },
            { icon: Wallet, title: 'Your own broker', desc: 'Connect Alpaca in Settings → Connections.' },
          ]}
          action={
            <button className="btn btn-primary" onClick={close}>
              Start using Plus
            </button>
          }
        />
      ) : user?.plus ? (
        <div className="plus-done">
          <p className="plus-done-lede">Everything is unlocked on this account.</p>
          <button className="btn btn-primary plus-cta" onClick={close}>
            Back to Paula
          </button>
        </div>
      ) : (
        <>
          <ul className="plus-feats">
            {FEATURES.map(([t, d]) => (
              <li key={t}>
                <span className="plus-feat-t">{t}</span>
                <span className="plus-feat-d">{d}</span>
              </li>
            ))}
          </ul>

          <div className="plus-plans" role="radiogroup" aria-label="Billing">
            {(Object.keys(PLANS) as Plan[]).map((p) => (
              <button
                key={p}
                role="radio"
                aria-checked={plan === p}
                className={'plus-plan' + (plan === p ? ' plus-plan-on' : '')}
                onClick={() => setPlan(p)}
              >
                <span className="plus-plan-label">{PLANS[p].label}</span>
                <span className="plus-plan-price mono">
                  {PLANS[p].price}
                  <small>{PLANS[p].per}</small>
                </span>
                <span className="plus-plan-note">{PLANS[p].note}</span>
              </button>
            ))}
          </div>

          {isGuest ? (
            <>
              <button
                className="btn btn-primary plus-cta"
                onClick={() => {
                  try {
                    sessionStorage.setItem('paula-auth-mode', 'signup')
                  } catch {
                    /* lands on sign-in */
                  }
                  close()
                  signOut()
                }}
              >
                Create a free account to continue
              </button>
              <p className="plus-fine">Plus is tied to your login — sign up, then upgrade in one tap.</p>
            </>
          ) : (
            <>
              <button className="btn btn-primary plus-cta" onClick={buy} disabled={busy}>
                {busy ? 'Processing…' : `Get Plus — ${PLANS[plan].price}${PLANS[plan].per}`}
              </button>
              {error && <p className="plus-error">{error}</p>}
              <p className="plus-fine">Demo checkout — no payment is taken.</p>
            </>
          )}
        </>
      )}
    </Sheet>
  )
}
