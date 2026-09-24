import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../lib/api'
import { useChrome } from '../../lib/chrome'
import { useWebSocket } from '../../lib/ws'

interface UpcomingRow {
  ticker: string
  next: { date_str?: string; days_away?: number } | null
  score: number
  lean: string
  stock_lean: string | null
  evidence: string[]
}

interface Candidate {
  ticker: string
  score: number
  drift: { note: string; surprise_pct: number | null; days_since: number | null }
  size: { shares: number; dollars: number; note: string }
  buyable: boolean
  fundamental_notes: string[]
  news: { headline: string; url: string }[]
}

interface Ranked<T> {
  rows?: T[]
  candidates?: T[]
  scanned: number
  note?: string
  cached_at?: number
}

type Channel = 'forecast' | 'research'

function useProgress() {
  const [progress, setProgress] = useState<Record<Channel, string | null>>({ forecast: null, research: null })
  useWebSocket((e) => {
    if (e.event !== 'work_progress') return
    const ch = e.data.channel as Channel
    if (ch !== 'forecast' && ch !== 'research') return
    const done = Number(e.data.done ?? 0)
    const total = Number(e.data.total ?? 0)
    setProgress((p) => ({ ...p, [ch]: total && done < total ? `${done}/${total}` : null }))
  })
  return progress
}

function when(ts?: number) {
  if (!ts) return ''
  const m = Math.round((Date.now() / 1000 - ts) / 60)
  return m < 1 ? 'just now' : `${m}m ago`
}

export function IdeasPanel() {
  const qc = useQueryClient()
  const { analyze } = useChrome()
  const progress = useProgress()
  // Both rankings take ~a minute on a cold server cache, so they only run
  // when asked for; after that the server keeps them for 15 minutes.
  const [run, setRun] = useState<{ upcoming: boolean; drift: boolean }>({ upcoming: false, drift: false })

  const upcoming = useQuery({
    queryKey: ['ideas-upcoming'],
    queryFn: () => api.get<Ranked<UpcomingRow>>('/api/forecast/upcoming?limit=10'),
    enabled: run.upcoming,
    staleTime: 15 * 60_000,
  })
  const drift = useQuery({
    queryKey: ['ideas-drift'],
    queryFn: () => api.get<Ranked<Candidate>>('/api/research/candidates?limit=10'),
    enabled: run.drift,
    staleTime: 15 * 60_000,
  })

  async function refresh(which: 'upcoming' | 'drift') {
    const url =
      which === 'upcoming' ? '/api/forecast/upcoming?limit=10&fresh=true' : '/api/research/candidates?limit=10&fresh=true'
    const key = which === 'upcoming' ? 'ideas-upcoming' : 'ideas-drift'
    await qc.fetchQuery({ queryKey: [key], queryFn: () => api.get(url), staleTime: 0 })
  }

  return (
    <div className="ideas">
      <p className="ideas-disclaimer">
        Research, not orders. Nothing here trades — autopilot never holds through an earnings report.
      </p>

      <section className="card">
        <header className="card-head">
          <div>
            <h2 className="card-title">Likely to beat</h2>
            <p className="card-desc">Reporting in the next 3 weeks, ranked by estimate revisions and beat history.</p>
          </div>
          <IdeasAction
            started={run.upcoming}
            fetching={upcoming.isFetching}
            progress={progress.forecast}
            cachedAt={upcoming.data?.cached_at}
            onStart={() => setRun((r) => ({ ...r, upcoming: true }))}
            onRefresh={() => refresh('upcoming')}
          />
        </header>
        {!run.upcoming && <p className="empty">Ranks about 40 upcoming reports — takes around 10 seconds.</p>}
        {upcoming.error && <p className="empty">{upcoming.error.message}</p>}
        {upcoming.data?.note && <p className="empty">{upcoming.data.note}</p>}
        {upcoming.data?.rows && upcoming.data.rows.length > 0 && (
          <ol className="ideas-list">
            {upcoming.data.rows.map((r) => (
              <li key={r.ticker} className="ideas-row">
                <div className="ideas-row-main">
                  <button className="ticker-link" onClick={() => analyze(r.ticker)}>
                    {r.ticker}
                  </button>
                  <span className={'badge ' + (r.score >= 0.3 ? 'badge-green' : r.score <= -0.3 ? 'badge-red' : '')}>{r.lean}</span>
                  {r.next?.date_str && (
                    <span className="ideas-when">
                      {r.next.date_str}
                      {r.next.days_away != null && ` · ${r.next.days_away}d`}
                    </span>
                  )}
                </div>
                {r.stock_lean && <p className="ideas-warn">Stock reaction: {r.stock_lean}</p>}
                <ul className="ideas-evidence">
                  {r.evidence.slice(0, 3).map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="card">
        <header className="card-head">
          <div>
            <h2 className="card-title">Post-earnings drift</h2>
            <p className="card-desc">Already reported, still inside the 60-day drift window after a surprise.</p>
          </div>
          <IdeasAction
            started={run.drift}
            fetching={drift.isFetching}
            progress={progress.research}
            cachedAt={drift.data?.cached_at}
            onStart={() => setRun((r) => ({ ...r, drift: true }))}
            onRefresh={() => refresh('drift')}
          />
        </header>
        {!run.drift && <p className="empty">Ranks recent reporters still drifting — takes around 15 seconds.</p>}
        {drift.error && <p className="empty">{drift.error.message}</p>}
        {drift.data?.note && <p className="empty">{drift.data.note}</p>}
        {drift.data?.candidates && drift.data.candidates.length > 0 && (
          <ol className="ideas-list">
            {drift.data.candidates.map((c) => (
              <li key={c.ticker} className="ideas-row">
                <div className="ideas-row-main">
                  <button className="ticker-link" onClick={() => analyze(c.ticker)}>
                    {c.ticker}
                  </button>
                  <span className={'badge ' + (c.buyable ? 'badge-green' : '')}>{c.buyable ? 'In window' : 'Watch'}</span>
                  {c.size.shares > 0 && (
                    <span className="ideas-when" title={c.size.note}>
                      ~{c.size.shares} sh · ${Math.round(c.size.dollars).toLocaleString()}
                    </span>
                  )}
                </div>
                <p className="ideas-evidence-line">{c.drift.note}</p>
                {c.news[0] && <p className="ideas-news">{c.news[0].headline}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  )
}

function IdeasAction(props: {
  started: boolean
  fetching: boolean
  progress: string | null
  cachedAt?: number
  onStart: () => void
  onRefresh: () => void
}) {
  if (!props.started) {
    return (
      <button className="btn btn-primary btn-sm" onClick={props.onStart}>
        Run ranking
      </button>
    )
  }
  if (props.fetching) {
    return <span className="ideas-status">{props.progress ? `Scoring ${props.progress}` : 'Scoring…'}</span>
  }
  return (
    <button className="btn btn-ghost btn-sm" onClick={props.onRefresh} title="Re-run now">
      Updated {when(props.cachedAt)} · Refresh
    </button>
  )
}
