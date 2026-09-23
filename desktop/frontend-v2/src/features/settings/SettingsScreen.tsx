import { useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { useChrome } from '../../lib/chrome'
import './settings.css'

interface AutopilotMode {
  key: string
  label: string
  tagline: string
  risk_per_trade: number
  max_positions: number
  daily_loss_limit: number
  rvol_min: number
}

interface ModesResponse {
  ok: boolean
  current: string
  modes: AutopilotMode[]
}

interface UserSettings {
  ok: boolean
  display_name?: string
  alpaca_key_set?: boolean
  alpaca_secret_set?: boolean
}

export function SettingsScreen() {
  const { user, isGuest } = useSession()
  const { openPlus } = useChrome()
  const [displayName, setDisplayName] = useState('')
  const [saved, setSaved] = useState(false)
  const [modes, setModes] = useState<ModesResponse | null>(null)
  const [diagnostics, setDiagnostics] = useState<string | null>(null)
  const [diagBusy, setDiagBusy] = useState(false)
  const [diagError, setDiagError] = useState<string | null>(null)

  useEffect(() => {
    if (isGuest) return
    api.get<UserSettings>('/api/auth/settings').then((s) => setDisplayName(s.display_name ?? ''))
    api.get<ModesResponse>('/api/autopilot/modes').then(setModes)
  }, [isGuest])

  async function saveName() {
    try {
      await api.post('/api/auth/settings', { display_name: displayName })
      setSaved(true)
      setTimeout(() => setSaved(false), 1500)
    } catch {
      /* surfaced implicitly by nothing changing — acceptable for this preview */
    }
  }

  async function runDiagnostics() {
    setDiagBusy(true)
    setDiagError(null)
    setDiagnostics(null)
    try {
      const res = await api.get<{ ok: boolean; verdict?: string }>('/api/autopilot/diagnostics')
      setDiagnostics(res.verdict ?? 'No verdict returned.')
    } catch (e) {
      setDiagError(e instanceof ApiError ? e.message : 'Could not run diagnostics.')
    } finally {
      setDiagBusy(false)
    }
  }

  if (isGuest) {
    return (
      <div className="settings-screen">
        <h1 className="settings-title">Settings</h1>
        <p className="settings-guest-note">Sign in to manage your account, connections, and autopilot preferences.</p>
      </div>
    )
  }

  return (
    <div className="settings-screen">
      <h1 className="settings-title">Settings</h1>

      <section className="settings-section">
        <h2 className="settings-section-title">Account</h2>
        <div className="settings-row">
          <span className="settings-row-label">Email</span>
          <span className="settings-row-value mono">{user?.email}</span>
        </div>
        <div className="settings-row">
          <span className="settings-row-label">Display name</span>
          <div className="settings-row-input-group">
            <input className="settings-input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            <button className="settings-save" onClick={saveName}>
              {saved ? '✓ Saved' : 'Save'}
            </button>
          </div>
        </div>
        <div className="settings-row">
          <span className="settings-row-label">Plan</span>
          <span className="settings-row-value settings-plan">
            {user?.plus ? 'Paula Plus' : 'Free'}
            {!user?.plus && (
              <button className="settings-save" onClick={openPlus}>
                Upgrade
              </button>
            )}
          </span>
        </div>
      </section>

      <section className="settings-section">
        <h2 className="settings-section-title">Autopilot strategy</h2>
        <p className="settings-section-note">
          Read-only in this preview build — the autonomous trading loop isn't wired up yet by design.
        </p>
        {modes && (
          <div className="settings-modes">
            {modes.modes.map((m) => (
              <div key={m.key} className={'settings-mode' + (modes.current === m.key ? ' settings-mode-on' : '')}>
                <div className="settings-mode-head">
                  <span className="settings-mode-label">{m.label}</span>
                  {modes.current === m.key && <span className="settings-mode-badge">active</span>}
                </div>
                <p className="settings-mode-tagline">{m.tagline}</p>
                <div className="settings-mode-stats mono">
                  risk {(m.risk_per_trade * 100).toFixed(1)}% · max {m.max_positions} positions · daily loss limit{' '}
                  {(m.daily_loss_limit * 100).toFixed(0)}% · RVOL ≥ {m.rvol_min}
                </div>
              </div>
            ))}
          </div>
        )}
        <button className="settings-diag-btn" onClick={runDiagnostics} disabled={diagBusy}>
          {diagBusy ? 'Running…' : 'Why no trades? →'}
        </button>
        {diagnostics && <div className="settings-diag-result">{diagnostics}</div>}
        {diagError && <div className="settings-diag-error">{diagError}</div>}
      </section>

      <section className="settings-section">
        <h2 className="settings-section-title">Connections</h2>
        {user?.plus ? (
          <p className="settings-section-note">Broker and data-feed keys — manage in your account.</p>
        ) : (
          <button className="settings-locked" onClick={openPlus}>
            <span>Connect your own Alpaca account</span>
            <span className="settings-locked-badge">PLUS</span>
          </button>
        )}
      </section>
    </div>
  )
}
