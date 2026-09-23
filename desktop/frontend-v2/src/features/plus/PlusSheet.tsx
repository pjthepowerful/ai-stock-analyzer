import { useState } from 'react'
import { Sheet } from '../../components/Sheet'
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
  ['Autopilot strategies', 'Core, strict and intense modes, with the daily loss limits you set.'],
]

interface Props {
  open: boolean
  onClose: () => void
}

export function PlusSheet({ open, onClose }: Props) {
  const { user, isGuest, refresh } = useSession()
  const [plan, setPlan] = useState<Plan>('annual')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function buy() {
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/plus/purchase', { plan })
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Checkout failed — nothing was charged.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet open={open} onClose={onClose} title={user?.plus ? 'You have Plus' : 'Paula Plus'}>
      {user?.plus ? (
        <div className="plus-done">
          <p className="plus-done-lede">Everything is unlocked on this account.</p>
          <button className="plus-cta" onClick={onClose}>
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
            <p className="plus-fine">Create an account first — Plus is tied to your login.</p>
          ) : (
            <>
              <button className="plus-cta" onClick={buy} disabled={busy}>
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
