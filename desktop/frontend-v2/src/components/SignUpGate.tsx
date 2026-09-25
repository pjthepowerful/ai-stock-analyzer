import { useSession } from '../lib/auth'
import './SignUpGate.css'

/** What guests see on a members-only screen: why, and a way in — not a dead
 *  end. "Create a free account" opens the sign-up form directly. */
export function SignUpGate({ text, className = '' }: { text: string; className?: string }) {
  const { signOut } = useSession()

  function go(mode: 'signup' | 'login') {
    try {
      sessionStorage.setItem('paula-auth-mode', mode)
    } catch {
      /* lands on sign-in */
    }
    signOut() // leaves guest mode for the auth screen
  }

  return (
    <div className={'card signup-gate ' + className}>
      <p className="signup-gate-text">{text}</p>
      <div className="signup-gate-actions">
        <button className="btn btn-primary btn-sm" onClick={() => go('signup')}>
          Create a free account
        </button>
        <button className="btn btn-secondary btn-sm" onClick={() => go('login')}>
          Sign in
        </button>
      </div>
      <p className="signup-gate-note">Free — no card needed.</p>
    </div>
  )
}
