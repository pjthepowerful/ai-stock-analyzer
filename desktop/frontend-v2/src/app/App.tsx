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
}

export default function App() {
  const { user, isGuest, loading, error } = useSession()
  const [maint, setMaint] = useState<Maintenance>({ on: false, message: '' })
  const [ownerSignIn, setOwnerSignIn] = useState(false)

  useEffect(() => {
    api
      .get<Maintenance>('/api/maintenance')
      .then((m) => setMaint({ on: !!m.on, message: m.message ?? '' }))
      .catch(() => {
        /* backend unreachable — screens surface their own errors */
      })
  }, [])

  useWebSocket((e) => {
    if (e.event === 'maintenance') {
      setMaint({ on: !!e.data.on, message: String(e.data.message ?? '') })
    }
  })

  if (loading) return null

  // The owner keeps full access so they can turn it back off. A signed-out
  // owner gets a quiet way to the sign-in screen; anyone else who signs in
  // that way just lands back here.
  if (maint.on && !user?.is_admin && !(ownerSignIn && !user)) {
    return (
      <div className="maint">
        <span className="maint-logo">P</span>
        <h1 className="maint-title">Paula is down for maintenance.</h1>
        <p className="maint-msg">{maint.message || "We'll be back shortly."}</p>
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
