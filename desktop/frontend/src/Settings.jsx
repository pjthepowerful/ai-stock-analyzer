import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://127.0.0.1:3141' : 'https://scurrilously-inevasible-kailey.ngrok-free.dev')

export default function Settings({ token, user, onClose, onLogout }) {
  const [keyId, setKeyId] = useState('')
  const [secret, setSecret] = useState('')
  const [label, setLabel] = useState('')
  const [provider, setProvider] = useState('alpaca_paper')
  const [providers, setProviders] = useState([])
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }

  useEffect(() => { loadKeys() }, [])

  const loadKeys = async () => {
    try {
      const res = await fetch(`${API}/api/auth/keys`, { headers })
      const data = await res.json()
      if (data.ok) setProviders(data.providers)
    } catch (e) {}
  }

  const saveKeys = async (e) => {
    e.preventDefault()
    if (!keyId || !secret) { setMsg('Both fields required'); return }
    setSaving(true)
    setMsg('')
    try {
      const res = await fetch(`${API}/api/auth/keys`, {
        method: 'POST', headers,
        body: JSON.stringify({ provider, key_id: keyId, secret, label })
      })
      const data = await res.json()
      if (data.ok) {
        setMsg('Keys saved & encrypted ✓')
        setKeyId('')
        setSecret('')
        setLabel('')
        loadKeys()
      } else {
        setMsg(data.error || 'Failed to save')
      }
    } catch (e) { setMsg('Backend error') }
    setSaving(false)
  }

  const deleteKeys = async (prov) => {
    await fetch(`${API}/api/auth/keys/${prov}`, { method: 'DELETE', headers })
    loadKeys()
  }

  return (
    <div className="settings-overlay">
      <div className="settings-panel">
        <div className="settings-header">
          <h2>Settings</h2>
          <button className="settings-close" onClick={onClose}>✕</button>
        </div>

        <div className="settings-section">
          <h3>Account</h3>
          <div className="settings-info">
            <span className="settings-label">Username</span>
            <span className="settings-value">{user?.username}</span>
          </div>
          <div className="settings-info">
            <span className="settings-label">Email</span>
            <span className="settings-value">{user?.email}</span>
          </div>
        </div>

        <div className="settings-section">
          <h3>Connected Brokers</h3>
          {providers.length > 0 ? (
            providers.map((p, i) => (
              <div key={i} className="settings-broker">
                <div>
                  <span className="broker-name">
                    {p.provider === 'alpaca_paper' ? '📄 Alpaca Paper' :
                     p.provider === 'alpaca_live' ? '💰 Alpaca Live' : p.provider}
                  </span>
                  {p.label && <span className="broker-label">{p.label}</span>}
                </div>
                <button className="broker-remove" onClick={() => deleteKeys(p.provider)}>Remove</button>
              </div>
            ))
          ) : (
            <p className="settings-empty">No broker connected. Add your API keys below.</p>
          )}
        </div>

        <div className="settings-section">
          <h3>Add API Keys</h3>
          <form onSubmit={saveKeys}>
            <select value={provider} onChange={e => setProvider(e.target.value)} className="auth-input">
              <option value="alpaca_paper">Alpaca Paper Trading</option>
              <option value="alpaca_live" disabled>Alpaca Live Trading (coming soon)</option>
            </select>
            <input
              type="text" placeholder="API Key ID" value={keyId}
              onChange={e => setKeyId(e.target.value)} className="auth-input"
            />
            <input
              type="password" placeholder="API Secret" value={secret}
              onChange={e => setSecret(e.target.value)} className="auth-input"
            />
            <input
              type="text" placeholder="Label (optional)" value={label}
              onChange={e => setLabel(e.target.value)} className="auth-input"
            />
            {msg && <p className={msg.includes('✓') ? 'auth-success' : 'auth-error'}>{msg}</p>}
            <button type="submit" className="auth-submit" disabled={saving}>
              {saving ? 'Saving...' : 'Save & Encrypt Keys'}
            </button>
          </form>
          <p className="settings-note">Keys are encrypted with AES-256 and stored locally on the server. They never leave this machine.</p>
        </div>

        <div className="settings-section">
          <button className="logout-btn" onClick={onLogout}>Log out</button>
        </div>
      </div>
    </div>
  )
}
