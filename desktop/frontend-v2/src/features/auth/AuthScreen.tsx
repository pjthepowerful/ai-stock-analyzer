import { CalendarDays, ChartCandlestick, Eye, EyeOff, Lightbulb } from 'lucide-react'
import { useState } from 'react'
import { ThemeSwitch } from '../../components/ThemeSwitch'
import { Typewriter } from '../../components/Typewriter'
import { useSession } from '../../lib/auth'
import './auth.css'

const TAGLINES = ['Know before you trade.', 'Every trade, reasoned through.', 'Setups that clear the bar.', 'Your market, explained.']

interface Props {
  /** Maintenance mode's owner door: sign in only — no guest, no sign-up. */
  ownerOnly?: boolean
  onBack?: () => void
}

export function AuthScreen({ ownerOnly = false, onBack }: Props = {}) {
  const { login, signup, continueAsGuest, error } = useSession()
  // "Create a free account" from guest chat lands straight on sign-up.
  const [mode, setMode] = useState<'login' | 'signup'>(() => {
    try {
      const m = sessionStorage.getItem('paula-auth-mode')
      sessionStorage.removeItem('paula-auth-mode')
      return m === 'signup' && !ownerOnly ? 'signup' : 'login'
    } catch {
      return 'login'
    }
  })
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)

  const signingUp = mode === 'signup'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      if (signingUp) await signup(username.trim(), email.trim(), password)
      else await login(email.trim(), password)
    } catch {
      // surfaced via session.error
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <section className="auth-side">
        <header className="auth-brand">
          <span className="brand-mark">P</span>
          <span className="brand-name">Paula</span>
          <span className="auth-brand-spacer" />
          <ThemeSwitch />
        </header>

        {/* Phones don't get the preview panel, so say what Paula is up front. */}
        {!ownerOnly && (
          <div className="auth-pitch">
            <p className="auth-pitch-tag">Know before you trade.</p>
            <ul>
              <li>
                <Lightbulb size={15} strokeWidth={1.8} /> Market scans that only surface setups clearing the full bar
              </li>
              <li>
                <ChartCandlestick size={15} strokeWidth={1.8} /> Signal, levels and a chart for any ticker — or send a screenshot
              </li>
              <li>
                <CalendarDays size={15} strokeWidth={1.8} /> Earnings calendar with a read on every report
              </li>
            </ul>
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-heading">
            <h1>{signingUp ? 'Create your account' : 'Welcome back'}</h1>
            <p>{signingUp ? 'Free to start — 3 messages a day, upgrade any time.' : 'Sign in to pick up where you left off.'}</p>
          </div>

          {signingUp && (
            <label className="auth-field">
              <span>Name</span>
              <input
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="name"
                minLength={2}
                required
              />
            </label>
          )}
          <label className="auth-field">
            <span>Email</span>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
              required
            />
          </label>
          <label className="auth-field">
            <span>Password</span>
            <span className="auth-pass">
              <input
                className="input"
                type={show ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={signingUp ? 'new-password' : 'current-password'}
                minLength={signingUp ? 6 : undefined}
                required
              />
              <button
                type="button"
                className="auth-eye"
                onClick={() => setShow((v) => !v)}
                aria-label={show ? 'Hide password' : 'Show password'}
              >
                {show ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </span>
            {signingUp && <small className="auth-hint">At least 6 characters.</small>}
          </label>

          {error && (
            <p className="auth-error" role="alert">
              {error}
            </p>
          )}

          <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
            {busy ? (signingUp ? 'Creating account…' : 'Signing in…') : signingUp ? 'Create account' : 'Sign in'}
          </button>

          {ownerOnly ? (
            <p className="auth-switch">
              Paula is in maintenance — only the owner can sign in.{' '}
              <button type="button" onClick={onBack}>
                Back
              </button>
            </p>
          ) : (
            <>
            <div className="auth-divider">
              <span>or</span>
            </div>

            <button type="button" className="btn btn-secondary auth-submit" onClick={continueAsGuest}>
              Continue as guest
            </button>

            <p className="auth-switch">
              {signingUp ? 'Already have an account?' : 'New to Paula?'}{' '}
              <button type="button" onClick={() => setMode(signingUp ? 'login' : 'signup')}>
                {signingUp ? 'Sign in' : 'Create an account'}
              </button>
            </p>
            </>
          )}
        </form>

        <p className="auth-legal">Paper trading only. Paula is research, not financial advice.</p>
      </section>

      <aside className="auth-show" aria-hidden>
        <div className="auth-show-inner">
          <h2 className="auth-tagline">
            <Typewriter phrases={TAGLINES} />
          </h2>

          <div className="auth-sample card">
            <div className="auth-sample-head">
              <div>
                <strong>AAPL</strong>
                <span>Apple Inc.</span>
              </div>
              <span className="badge">Example</span>
            </div>
            <div className="auth-sample-verdict">
              <span className="badge badge-green">BUY</span>
              <span>Pullback in uptrend</span>
            </div>
            <div className="auth-sample-score">
              <span>Score</span>
              <strong>81</strong>
              <span className="auth-sample-track">
                <span style={{ width: '81%' }} />
              </span>
            </div>
            <dl className="auth-sample-levels">
              <div>
                <dt>Entry</dt>
                <dd>$337.02</dd>
              </div>
              <div>
                <dt>Stop</dt>
                <dd className="negative">$322.76</dd>
              </div>
              <div>
                <dt>Target</dt>
                <dd className="positive">$379.80</dd>
              </div>
            </dl>
          </div>

          <ul className="auth-points">
            <li>
              <Lightbulb size={15} /> Market scans that only surface setups clearing the full bar
            </li>
            <li>
              <ChartCandlestick size={15} /> Signal, levels, chart and research for any ticker
            </li>
            <li>
              <CalendarDays size={15} /> Earnings calendar with a read on every report
            </li>
          </ul>
        </div>
      </aside>
    </div>
  )
}
