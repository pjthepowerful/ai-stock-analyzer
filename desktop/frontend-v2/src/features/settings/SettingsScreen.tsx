import { useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { useChrome } from '../../lib/chrome'
import { useToast } from '../../lib/toast'
import { ThemeSwitch } from '../../components/ThemeSwitch'
import { AutopilotPanel } from './AutopilotPanel'
import './settings.css'

interface UserSettings {
  ok: boolean
  display_name: string
  alpaca_connected: boolean
}

export function SettingsScreen() {
  const { user, isGuest } = useSession()
  const { openPlus } = useChrome()
  const toast = useToast()
  const [displayName, setDisplayName] = useState('')
  const [saved, setSaved] = useState(false)
  const [nameError, setNameError] = useState<string | null>(null)
  const [alpacaConnected, setAlpacaConnected] = useState(false)

  useEffect(() => {
    if (isGuest) return
    api.get<UserSettings>('/api/auth/settings').then((s) => {
      setDisplayName(s.display_name ?? '')
      setAlpacaConnected(s.alpaca_connected)
    })
  }, [isGuest])

  async function saveName() {
    setNameError(null)
    try {
      await api.post('/api/auth/settings', { display_name: displayName.trim() })
      setSaved(true)
      setTimeout(() => setSaved(false), 1500)
      toast.show('Display name saved')
    } catch (e) {
      setNameError(e instanceof ApiError ? e.message : 'Could not save.')
    }
  }

  if (isGuest) {
    return (
      <div className="page">
        <div className="page-inner page-inner-narrow">
        <header className="page-head">
          <div>
            <h1 className="page-title">Settings</h1>
            <p className="page-sub">Appearance, account and connections</p>
          </div>
        </header>
        <Appearance />
        <p className="card empty">Sign in to manage your account, connections, and autopilot preferences.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-inner page-inner-narrow">
      <header className="page-head">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-sub">Appearance, account and connections</p>
        </div>
      </header>

      <Appearance />

      <section className="settings-section">
        <h2 className="settings-section-title">Account</h2>
        <div className="settings-row">
          <span className="settings-row-label">Email</span>
          <span className="settings-row-value mono">{user?.email}</span>
        </div>
        <div className="settings-row">
          <span className="settings-row-label">Display name</span>
          <div className="settings-row-input-group">
            <input className="input settings-name-input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            <button className="btn btn-secondary btn-sm" onClick={saveName}>
              {saved ? '✓ Saved' : 'Save'}
            </button>
          </div>
        </div>
        {nameError && <div className="settings-diag-error">{nameError}</div>}
        <div className="settings-row">
          <span className="settings-row-label">Plan</span>
          <span className="settings-row-value settings-plan">
            {user?.plus ? 'Paula Plus' : 'Free'}
            {!user?.plus && (
              <button className="btn btn-secondary btn-sm" onClick={openPlus}>
                Upgrade
              </button>
            )}
          </span>
        </div>
      </section>

      {user?.can_autopilot && <AutopilotPanel />}

      <section className="settings-section">
        <h2 className="settings-section-title">Connections</h2>
        {user?.plus || user?.is_admin ? (
          <AlpacaConnection connected={alpacaConnected} onChange={setAlpacaConnected} />
        ) : (
          <button className="settings-locked" onClick={openPlus}>
            <span>Connect your own Alpaca account</span>
            <span className="settings-locked-badge">PLUS</span>
          </button>
        )}
      </section>
      </div>
    </div>
  )
}

function AlpacaConnection({ connected, onChange }: { connected: boolean; onChange: (c: boolean) => void }) {
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [keyId, setKeyId] = useState('')
  const [secret, setSecret] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [equity, setEquity] = useState<number | null>(null)

  async function connect(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await api.post<{ alpaca?: { equity: number } }>('/api/auth/settings', {
        alpaca_key: keyId.trim(),
        alpaca_secret: secret.trim(),
      })
      setEquity(res.alpaca?.equity ?? null)
      setKeyId('')
      setSecret('')
      setEditing(false)
      onChange(true)
      toast.show('Alpaca account connected')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not connect.')
    } finally {
      setBusy(false)
    }
  }

  async function disconnect() {
    setBusy(true)
    setError(null)
    try {
      await api.del('/api/auth/connections/alpaca')
      setEquity(null)
      onChange(false)
      toast.show('Alpaca account disconnected')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not disconnect.')
    } finally {
      setBusy(false)
    }
  }

  if (connected && !editing) {
    return (
      <div className="settings-conn">
        <div className="settings-row">
          <span className="settings-row-label">Alpaca (paper)</span>
          <span className="settings-row-value settings-conn-on">
            Connected
            {equity != null && (
              <span className="mono"> · ${equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            )}
          </span>
        </div>
        <div className="settings-conn-actions">
          <button className="btn btn-secondary btn-sm" onClick={() => setEditing(true)} disabled={busy}>
            Replace keys
          </button>
          <button className="btn btn-ghost btn-sm" onClick={disconnect} disabled={busy}>
            Disconnect
          </button>
        </div>
        {error && <div className="settings-diag-error">{error}</div>}
      </div>
    )
  }

  return (
    <form className="settings-conn" onSubmit={connect}>
      <p className="settings-section-note">
        Trade your own Alpaca paper account instead of the shared one. Keys are checked with Alpaca before saving and
        stored encrypted; Paula never shows them again.
      </p>
      <label className="settings-field">
        <span>API key ID</span>
        <input
          className="input mono"
          value={keyId}
          onChange={(e) => setKeyId(e.target.value)}
          autoComplete="off"
          spellCheck={false}
        />
      </label>
      <label className="settings-field">
        <span>Secret key</span>
        <input
          className="input mono"
          type="password"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          autoComplete="new-password"
        />
      </label>
      <div className="settings-conn-actions">
        <button className="btn btn-secondary btn-sm" type="submit" disabled={busy || !keyId.trim() || !secret.trim()}>
          {busy ? 'Checking with Alpaca…' : 'Connect'}
        </button>
        {editing && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>
            Cancel
          </button>
        )}
      </div>
      {error && <div className="settings-diag-error">{error}</div>}
    </form>
  )
}

function Appearance() {
  return (
    <section className="settings-section">
      <h2 className="settings-section-title">Appearance</h2>
      <div className="settings-row">
        <span className="settings-row-label">Theme</span>
        <ThemeSwitch labels />
      </div>
    </section>
  )
}
