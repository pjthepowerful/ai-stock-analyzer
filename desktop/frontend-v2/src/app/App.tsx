import { useEffect, useState } from 'react'
import { AuthScreen } from '../features/auth/AuthScreen'
import { api } from '../lib/api'
import { useSession } from '../lib/auth'
import { useWebSocket } from '../lib/ws'
import { Shell } from './Shell'
import './maintenance.css'

interface Maintenance {
  on: boolean
  message: string
  /** Unix seconds the owner expects to be back, if they set one. */
  eta?: number | null
}

/** "Back in about 25 minutes", ticking down while the screen is open. */
function Eta({ at }: { at: number }) {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 15_000)
    return () => clearInterval(id)
  }, [])
  const mins = Math.ceil((at - now) / 60)
  const when = new Date(at * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  let text: string
  if (mins <= 0) text = 'Should be back any minute now.'
  else if (mins < 60) text = `Back in about ${mins} minute${mins === 1 ? '' : 's'}`
  else {
    const h = Math.round(mins / 6) / 10
    text = `Back in about ${h} hour${h === 1 ? '' : 's'}`
  }
  return (
    <p className="maint-eta">
      <span className="maint-eta-dot" />
      {text}
      {mins > 0 && <span className="maint-eta-at"> · around {when}</span>}
    </p>
  )
}

export default function App() {
  const { user, isGuest, loading, error } = useSession()
  const [maint, setMaint] = useState<Maintenance>({ on: false, message: '' })
  const [ownerSignIn, setOwnerSignIn] = useState(false)

  useEffect(() => {
    api
      .get<Maintenance>('/api/maintenance')
      .then((m) => setMaint({ on: !!m.on, message: m.message ?? '', eta: m.eta }))
      .catch(() => {
        /* backend unreachable — screens surface their own errors */
      })
  }, [])

  useWebSocket((e) => {
    if (e.event === 'maintenance') {
      setMaint({ on: !!e.data.on, message: String(e.data.message ?? ''), eta: (e.data.eta as number | null) ?? null })
    }
  })

  if (loading) return null

  // The owner keeps full access so they can turn it back off. A signed-out
  // owner gets a quiet way to the sign-in screen; anyone else who signs in
  // that way just lands back here.
  // The owner door is sign-in only: a guest session or a non-owner account
  // lands right back here (and the server refuses their API calls anyway).
  if (maint.on && !user?.is_admin) {
    if (ownerSignIn && !user && !isGuest) {
      return <AuthScreen ownerOnly onBack={() => setOwnerSignIn(false)} />
    }
    return (
      <div className="maint">
        <span className="maint-logo">P</span>
        <h1 className="maint-title">Paula is down for maintenance.</h1>
        <p className="maint-msg">{maint.message || "We'll be back shortly."}</p>
        {maint.eta ? <Eta at={maint.eta} /> : null}
        {!user && !isGuest && (
          <button className="maint-door" onClick={() => setOwnerSignIn(true)}>
            Owner sign-in
          </button>
        )}
      </div>
    )
  }

  if (!user && !isGuest) {
    // Still holding a token means the backend was unreachable, not that
    // you're signed out — don't show a login form for that.
    if (error && localStorage.getItem('paula-v2-token')) {
      return (
        <div className="maint">
          <span className="maint-logo">P</span>
          <h1 className="maint-title">Can’t reach Paula.</h1>
          <p className="maint-msg">The server didn’t answer. You’re still signed in.</p>
          <button className="maint-door" onClick={() => location.reload()}>
            Try again
          </button>
        </div>
      )
    }
    return <AuthScreen />
  }

  return <Shell />
}
