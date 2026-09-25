import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Rocket } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { fromLocalInput, toLocalInput, whenLabel } from '../launch/ComingSoon'
import { OWNER_PREVIEW } from '../launch/LaunchGate'
import { LaunchVideo } from '../launch/LaunchVideo'

interface LaunchStatus {
  launch_at: number | null
  now: number
  live: boolean
}

const QUICK = [1, 3, 5, 15, 60]

function countdown(secs: number) {
  if (secs <= 0) return 'now'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  return h ? `${h}h ${m}m` : m ? `${m}m ${String(s).padStart(2, '0')}s` : `${s}s`
}

/** Redo the Paula 5 launch: put the countdown page back up for everyone and
 *  pick when it opens. Same owner login + launch phrase as the Team panel. */
export function LaunchPanel() {
  const qc = useQueryClient()
  const status = useQuery({
    queryKey: ['launch'],
    queryFn: () => api.get<LaunchStatus>('/api/launch'),
    refetchInterval: 15_000,
  })
  const [phrase, setPhrase] = useState('')
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [confirmNow, setConfirmNow] = useState(false)
  const [video, setVideo] = useState(false)
  const [now, setNow] = useState(() => Date.now() / 1000)

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(id)
  }, [])

  const s = status.data
  const skew = s ? s.now - status.dataUpdatedAt / 1000 : 0
  const left = s?.launch_at ? s.launch_at - (now + skew) : 0
  const counting = !!s && !s.live && left > 0

  async function setLaunch(at: number, label: string) {
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      await api.post('/api/launch/set', { phrase, launch_at: at })
      // Keep this tab in the app instead of flipping to the countdown page.
      try {
        sessionStorage.setItem(OWNER_PREVIEW, '1')
      } catch {
        /* the gate just shows you the countdown instead */
      }
      await qc.invalidateQueries({ queryKey: ['launch'] })
      setDone(label)
      setConfirmNow(false)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const ready = phrase.trim().length > 0 && !busy

  return (
    <section className="card admin-panel admin-launch">
      <div className="admin-launch-status">
        <span className={'admin-launch-dot' + (counting ? ' admin-launch-dot-wait' : '')} />
        {!s ? (
          <span className="text-dim">Checking launch status…</span>
        ) : counting ? (
          <span>
            Countdown is up — opens in <strong className="mono">{countdown(left)}</strong>
            <span className="text-dim"> · {whenLabel(s.launch_at!)}</span>
          </span>
        ) : (
          <span>
            Paula 5 is live
            {s.launch_at ? <span className="text-dim"> · since {whenLabel(s.launch_at)}</span> : null}
          </span>
        )}
      </div>

      <p className="admin-dim">
        Redoing the launch puts the coming-soon countdown back up for everyone except you. When it hits zero the site
        opens and the launch video plays again — even for people who already watched it.
      </p>

      <label className="admin-maint-label" htmlFor="launch-phrase">
        Launch phrase
      </label>
      <input
        id="launch-phrase"
        className="input admin-filter"
        type="password"
        autoComplete="off"
        placeholder="Needed for every change"
        value={phrase}
        onChange={(e) => setPhrase(e.target.value)}
      />

      <p className="admin-maint-label">Relaunch in</p>
      <div className="admin-launch-quick">
        {QUICK.map((m) => (
          <button
            key={m}
            className="btn btn-secondary btn-sm"
            disabled={!ready}
            onClick={() => setLaunch(Date.now() / 1000 + m * 60, `Countdown set — opens in ${m < 60 ? `${m} min` : '1 hour'}.`)}
          >
            {m < 60 ? `${m} min` : '1 hour'}
          </button>
        ))}
      </div>

      <label className="admin-maint-label" htmlFor="launch-at">
        Or pick a time (Central)
      </label>
      <div className="admin-launch-row">
        <input
          id="launch-at"
          className="input admin-filter"
          type="datetime-local"
          value={draft || (s?.launch_at ? toLocalInput(Math.max(s.launch_at, now)) : '')}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button
          className="btn btn-secondary btn-sm"
          disabled={!ready || !draft}
          onClick={() => setLaunch(fromLocalInput(draft), 'Launch time saved.')}
        >
          Set time
        </button>
      </div>

      <div className="admin-maint-actions admin-launch-actions">
        {counting &&
          (confirmNow ? (
            <>
              <span className="text-dim">Open to everyone right now?</span>
              <button className="btn btn-primary btn-sm" disabled={!ready} onClick={() => setLaunch(Date.now() / 1000, 'Paula 5 is live.')}>
                <Rocket size={13} />
                Yes, launch now
              </button>
              <button className="admin-link" onClick={() => setConfirmNow(false)}>
                cancel
              </button>
            </>
          ) : (
            <button className="btn btn-primary btn-sm" disabled={!ready} onClick={() => setConfirmNow(true)}>
              <Rocket size={13} />
              Launch now…
            </button>
          ))}
        <button className="btn btn-secondary btn-sm" onClick={() => setVideo(true)}>
          <Play size={13} />
          Preview video
        </button>
      </div>

      {done && <p className="admin-launch-done">{done}</p>}
      {error && <p className="admin-error">{error}</p>}
      {video && <LaunchVideo onDone={() => setVideo(false)} />}
    </section>
  )
}
