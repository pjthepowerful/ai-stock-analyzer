import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Power } from 'lucide-react'
import { useState } from 'react'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { api, ApiError } from '../../lib/api'
import { useToast } from '../../lib/toast'
import { useWebSocket } from '../../lib/ws'

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

interface Activity {
  at: string
  kind: 'started' | 'stopped' | 'resumed' | 'restarted' | 'paused' | 'cycle' | 'error'
  reason?: string
  error?: string
  scanned?: number
  opportunities?: number
  buys?: number
  sells?: number
  shorts?: number
}

interface StatusResponse {
  ok: boolean
  running: boolean
  mode: string
  started_at?: number | null
  recent?: Activity[]
}

function describe(a: Activity): string {
  switch (a.kind) {
    case 'started':
      return 'Started'
    case 'stopped':
      return 'Stopped'
    case 'resumed':
      return 'Resumed after a restart'
    case 'restarted':
      return 'Recovered from a crash'
    case 'paused':
      return a.reason || 'Market closed — waiting'
    case 'error':
      return `Error: ${a.error ?? 'unknown'}`
    case 'cycle': {
      const trades = [
        a.buys ? `${a.buys} bought` : '',
        a.shorts ? `${a.shorts} shorted` : '',
        a.sells ? `${a.sells} closed` : '',
      ].filter(Boolean)
      return `Scanned ${a.scanned ?? 0}, ${a.opportunities ?? 0} setups` + (trades.length ? ` · ${trades.join(', ')}` : '')
    }
  }
}

export function AutopilotPanel() {
  const qc = useQueryClient()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [diagnostics, setDiagnostics] = useState<string | null>(null)
  const [diagBusy, setDiagBusy] = useState(false)

  const status = useQuery({
    queryKey: ['autopilot-status'],
    queryFn: () => api.get<StatusResponse>('/api/autopilot/status'),
    refetchInterval: 30_000,
  })
  const modes = useQuery({
    queryKey: ['autopilot-modes'],
    queryFn: () => api.get<ModesResponse>('/api/autopilot/modes'),
  })

  useWebSocket((e) => {
    if (e.event === 'autopilot') void qc.invalidateQueries({ queryKey: ['autopilot-status'] })
  })

  const running = !!status.data?.running
  const current = modes.data?.current ?? status.data?.mode

  async function toggle() {
    setBusy(true)
    setError(null)
    try {
      await api.post(running ? '/api/autopilot/stop' : '/api/autopilot/start', {})
      toast.show(running ? 'Autopilot stopped' : 'Autopilot started')
      await qc.invalidateQueries({ queryKey: ['autopilot-status'] })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not reach Paula.')
    } finally {
      setBusy(false)
    }
  }

  // Picking a strategy opens a confirm; the switch happens on Confirm.
  const [pending, setPending] = useState<AutopilotMode | null>(null)
  const [switching, setSwitching] = useState(false)
  const [switchError, setSwitchError] = useState<string | null>(null)

  function pickMode(m: AutopilotMode) {
    if (running || m.key === current) return
    setSwitchError(null)
    setPending(m)
  }

  async function confirmMode() {
    if (!pending) return
    setSwitching(true)
    setSwitchError(null)
    try {
      await api.post('/api/autopilot/mode', { mode: pending.key })
      toast.show(`Switched to ${pending.label}`)
      setPending(null)
      await qc.invalidateQueries({ queryKey: ['autopilot-modes'] })
      await qc.invalidateQueries({ queryKey: ['autopilot-status'] })
    } catch (e) {
      setSwitchError(e instanceof ApiError ? e.message : 'Could not switch strategy.')
    } finally {
      setSwitching(false)
    }
  }

  const currentLabel = modes.data?.modes.find((m) => m.key === current)?.label ?? current

  async function runDiagnostics() {
    setDiagBusy(true)
    setDiagnostics(null)
    try {
      const res = await api.get<{ ok: boolean; verdict?: string }>('/api/autopilot/diagnostics')
      setDiagnostics(res.verdict ?? 'No verdict returned.')
    } catch (e) {
      setDiagnostics(e instanceof ApiError ? e.message : 'Could not run diagnostics.')
    } finally {
      setDiagBusy(false)
    }
  }

  const recent = status.data?.recent ?? []

  return (
    <section className="settings-section">
      <h2 className="settings-section-title">Autopilot</h2>

      <div className="ap-head">
        <div className="ap-state">
          <span className={'ap-dot' + (running ? ' ap-dot-on' : '')} />
          <div>
            <strong>{status.isLoading ? 'Checking…' : running ? 'Running' : 'Off'}</strong>
            <p className="settings-section-note">
              {running
                ? 'Scanning every 5 minutes while the market is open, on your Alpaca paper account.'
                : 'When on, Paula scans and places paper trades on its own, even with this tab closed.'}
            </p>
          </div>
        </div>
        <button className={'btn ' + (running ? 'btn-secondary' : 'btn-primary')} onClick={toggle} disabled={busy || status.isLoading}>
          <Power size={14} />
          {busy ? (running ? 'Stopping…' : 'Starting…') : running ? 'Stop' : 'Start'}
        </button>
      </div>
      {error && <div className="settings-diag-error">{error}</div>}

      {modes.data && (
        <>
          <p className="settings-section-note">
            Strategy{running ? ' — stop autopilot to switch; open positions stay with the strategy that opened them.' : ''}
            {current && !modes.data.modes.some((m) => m.key === current) && (
              <> · Currently on the original <strong>{current}</strong> strategy — pick one below to switch.</>
            )}
          </p>
          <div className="settings-modes">
            {modes.data.modes.map((m) => (
              <button
                key={m.key}
                className={'settings-mode' + (current === m.key ? ' settings-mode-on' : '')}
                onClick={() => pickMode(m)}
                disabled={running && current !== m.key}
                aria-pressed={current === m.key}
              >
                <div className="settings-mode-head">
                  <span className="settings-mode-label">{m.label}</span>
                  {current === m.key && <span className="settings-mode-badge">active</span>}
                </div>
                <p className="settings-mode-tagline">{m.tagline}</p>
                <div className="settings-mode-stats mono">
                  risk {(m.risk_per_trade * 100).toFixed(1)}% · max {m.max_positions} positions · daily loss limit{' '}
                  {(m.daily_loss_limit * 100).toFixed(0)}% · RVOL ≥ {m.rvol_min}
                </div>
              </button>
            ))}
          </div>
        </>
      )}

      {recent.length > 0 && (
        <div className="ap-activity">
          <p className="settings-section-note">Recent activity</p>
          <ul>
            {recent.slice(0, 8).map((a, i) => (
              <li key={i} className={a.kind === 'error' ? 'ap-error' : undefined}>
                <span className="mono ap-time">
                  {new Date(a.at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                </span>
                {describe(a)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <button className="btn btn-secondary" onClick={runDiagnostics} disabled={diagBusy}>
        {diagBusy ? 'Running…' : 'Why no trades? →'}
      </button>
      {diagnostics && <div className="settings-diag-result">{diagnostics}</div>}

      <ConfirmDialog
        open={!!pending}
        title={`Switch to ${pending?.label ?? ''}?`}
        confirmLabel={`Switch to ${pending?.label ?? ''}`}
        busy={switching}
        error={switchError}
        onCancel={() => setPending(null)}
        onConfirm={confirmMode}
        body={
          pending && (
            <>
              <p>
                The next time autopilot runs it trades with <strong>{pending.label}</strong> instead of{' '}
                <strong>{currentLabel}</strong>.
              </p>
              <p>
                {pending.label} risks {(pending.risk_per_trade * 100).toFixed(1)}% per trade, holds up to{' '}
                {pending.max_positions} positions and stops for the day at a{' '}
                {(pending.daily_loss_limit * 100).toFixed(0)}% loss.
              </p>
            </>
          )
        }
      />
    </section>
  )
}
