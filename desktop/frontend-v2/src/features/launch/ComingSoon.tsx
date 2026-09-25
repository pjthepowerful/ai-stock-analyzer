import { useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { LaunchVideo } from './LaunchVideo'
import './comingsoon.css'

interface Props {
  launchAt: number
  /** Server clock minus this device's clock, so the countdown can't be
   *  moved by changing the computer's time. */
  skew: number
  onChanged: () => void
  /** Owner only: step past the gate to check the new site before launch. */
  onPreview: () => void
}

const CT = 'America/Chicago'

function parts(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000))
  return { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60 }
}

const pad = (n: number) => String(n).padStart(2, '0')

function whenLabel(at: number) {
  return new Date(at * 1000).toLocaleString(undefined, {
    timeZone: CT,
    weekday: 'long',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  })
}

/** The old Paula look (#141419, Outfit, JetBrains Mono, the green P) on
 *  purpose — this is the last screen of the old site. */
export function ComingSoon({ launchAt, skew, onChanged, onPreview }: Props) {
  const [now, setNow] = useState(() => Date.now() + skew)
  const [team, setTeam] = useState(false)

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() + skew), 250)
    return () => clearInterval(id)
  }, [skew])

  const left = parts(launchAt * 1000 - now)

  return (
    <div className="cs">
      <div className="cs-glow" aria-hidden />
      <div className="cs-card">
        <div className="cs-logo">P</div>
        <p className="cs-kicker">Paula 5</p>
        <h1 className="cs-title">Something new is coming.</h1>
        <p className="cs-sub">
          A whole new Paula — rebuilt from the ground up. We’re putting on the finishing touches; the doors open{' '}
          <strong>{whenLabel(launchAt)}</strong>.
        </p>

        <div className="cs-timer" role="timer" aria-live="off">
          {left.d > 0 && <Unit n={left.d} label="days" />}
          <Unit n={left.h} label="hours" />
          <Unit n={left.m} label="min" />
          <Unit n={left.s} label="sec" />
        </div>

        <div className="cs-pulse" aria-hidden>
          <span />
          <span />
          <span />
        </div>
      </div>

      <button className="cs-team" onClick={() => setTeam(true)}>
        Team
      </button>
      {team && <TeamPanel launchAt={launchAt} now={now} onClose={() => setTeam(false)} onChanged={onChanged} onPreview={onPreview} />}
    </div>
  )
}

function Unit({ n, label }: { n: number; label: string }) {
  return (
    <div className="cs-unit">
      <span className="cs-num">{pad(n)}</span>
      <span className="cs-lbl">{label}</span>
    </div>
  )
}

// ── Owner controls: admin sign-in → launch phrase → timer ──────────────────

function toLocalInput(at: number) {
  // datetime-local in Central time, e.g. 2026-09-24T20:00
  const f = new Intl.DateTimeFormat('en-CA', {
    timeZone: CT,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(at * 1000))
  const g = (t: string) => f.find((p) => p.type === t)?.value ?? '00'
  return `${g('year')}-${g('month')}-${g('day')}T${g('hour')}:${g('minute')}`
}

function fromLocalInput(v: string): number {
  // Interpret the typed wall-clock time as Central, whatever the device's zone.
  const guess = new Date(v + ':00Z').getTime()
  const asCt = new Date(new Date(guess).toLocaleString('en-US', { timeZone: CT })).getTime()
  const asUtc = new Date(new Date(guess).toLocaleString('en-US', { timeZone: 'UTC' })).getTime()
  return (guess + (asUtc - asCt)) / 1000
}

function TeamPanel({
  launchAt,
  now,
  onClose,
  onChanged,
  onPreview,
}: {
  launchAt: number
  now: number
  onClose: () => void
  onChanged: () => void
  onPreview: () => void
}) {
  const { user, login } = useSession()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [phrase, setPhrase] = useState('')
  const [unlocked, setUnlocked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState(() => toLocalInput(launchAt))
  const [video, setVideo] = useState(false)
  const [confirmNow, setConfirmNow] = useState(false)

  const step = !user?.is_admin ? 'login' : !unlocked ? 'phrase' : 'panel'

  async function run(fn: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const save = (at: number) =>
    run(async () => {
      await api.post('/api/launch/set', { phrase, launch_at: at })
      onChanged()
      if (at) setDraft(toLocalInput(at))
    })

  // Never nudge into the past — that would open the site immediately.
  const nudge = (mins: number) => save(Math.max(now / 1000 + 30, launchAt + mins * 60))

  return (
    <div className="cs-sheet-back" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="cs-sheet" role="dialog" aria-label="Team">
        <button className="cs-x" onClick={onClose} aria-label="Close">
          ×
        </button>

        {step === 'login' && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              run(() => login(email.trim(), password))
            }}
          >
            <h2>Team sign-in</h2>
            <p className="cs-hint">Owner account only.</p>
            {user && !user.is_admin && <p className="cs-err">This account can’t open the launch controls.</p>}
            <input className="cs-in" type="email" placeholder="Email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
            <input className="cs-in" type="password" placeholder="Password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button className="cs-btn" disabled={busy || !email || !password}>
              {busy ? 'Signing in…' : 'Continue'}
            </button>
          </form>
        )}

        {step === 'phrase' && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              run(async () => {
                await api.post('/api/launch/unlock', { phrase })
                setUnlocked(true)
              })
            }}
          >
            <h2>Launch phrase</h2>
            <p className="cs-hint">Type the phrase to open the launch controls.</p>
            <input className="cs-in" type="password" autoComplete="off" autoFocus placeholder="Phrase" value={phrase} onChange={(e) => setPhrase(e.target.value)} />
            <button className="cs-btn" disabled={busy || !phrase}>
              {busy ? 'Checking…' : 'Unlock'}
            </button>
          </form>
        )}

        {step === 'panel' && (
          <div>
            <h2>Launch controls</h2>
            <p className="cs-hint">
              Opens for everyone at <strong>{whenLabel(launchAt)}</strong>. When the timer hits zero the site goes live on
              its own and the new video plays.
            </p>
            <div className="cs-nudges">
              {[-60, -15, 15, 60].map((m) => (
                <button key={m} className="cs-chip" disabled={busy} onClick={() => nudge(m)}>
                  {m > 0 ? '+' : '−'}
                  {Math.abs(m) >= 60 ? `${Math.abs(m) / 60}h` : `${Math.abs(m)}m`}
                </button>
              ))}
            </div>
            <label className="cs-label">
              Launch time (Central)
              <input className="cs-in" type="datetime-local" value={draft} onChange={(e) => setDraft(e.target.value)} />
            </label>
            <button className="cs-btn" disabled={busy || !draft} onClick={() => save(fromLocalInput(draft))}>
              {busy ? 'Saving…' : 'Set launch time'}
            </button>
            {confirmNow ? (
              <div className="cs-confirm">
                <span>Open Paula 5 to everyone right now?</span>
                <button className="cs-btn cs-btn-go" disabled={busy} onClick={() => save(0)}>
                  Yes, launch now
                </button>
                <button className="cs-link" onClick={() => setConfirmNow(false)}>
                  Cancel
                </button>
              </div>
            ) : (
              <button className="cs-link" onClick={() => setConfirmNow(true)}>
                Launch now…
              </button>
            )}
            <button className="cs-btn cs-btn-ghost" onClick={() => setVideo(true)}>
              ▶ Preview launch video
            </button>
            <button className="cs-link" onClick={onPreview}>
              Preview Paula 5 (only you) →
            </button>
          </div>
        )}

        {error && <p className="cs-err">{error}</p>}
      </div>
      {video && <LaunchVideo onDone={() => setVideo(false)} />}
    </div>
  )
}
