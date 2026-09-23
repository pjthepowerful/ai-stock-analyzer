import { useState } from 'react'
import { useSession } from '../../lib/auth'
import './auth.css'

export function AuthScreen() {
  const { login, signup, continueAsGuest, error } = useSession()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      if (mode === 'login') await login(email, password)
      else await signup(username, email, password)
    } catch {
      // error already surfaced via session.error
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-hero">
        <span className="auth-eyebrow">PAULA — PREVIEW BUILD</span>
        <h1 className="auth-headline">
          Every trade,
          <br />
          reasoned through.
        </h1>
        <p className="auth-sub">A rebuilt Paula — same engine, new everything else.</p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <h2 className="auth-form-title">{mode === 'login' ? 'Sign in' : 'Create account'}</h2>

        {mode === 'signup' && (
          <label className="auth-field">
            <span>Name</span>
            <input value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
        )}
        <label className="auth-field">
          <span>Email</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="auth-field">
          <span>Password</span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>

        {error && <div className="auth-error">{error}</div>}

        <button className="auth-submit" type="submit" disabled={busy}>
          {busy ? '…' : mode === 'login' ? 'Sign in →' : 'Create account →'}
        </button>

        <button
          type="button"
          className="auth-toggle"
          onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
        >
          {mode === 'login' ? "New to Paula? Create account" : 'Already have an account? Sign in'}
        </button>

        <div className="auth-divider">or</div>

        <button type="button" className="auth-guest" onClick={continueAsGuest}>
          Continue as guest
        </button>
      </form>
    </div>
  )
}
