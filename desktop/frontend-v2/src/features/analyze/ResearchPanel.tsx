import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { SignUpGate } from '../../components/SignUpGate'

interface Forecast {
  score: number | null
  lean: string | null
  stock_lean: string | null
  next: { date_str?: string; days_away?: number } | null
  evidence: string[]
}

interface Earnings {
  next: { date_str?: string; days_away?: number } | null
  last: { date_str?: string; days_ago?: number; eps_estimate?: number; eps_actual?: number; surprise_pct?: number } | null
  blocked: boolean
  block_reason: string
}

interface Research {
  news: { headline: string; source: string; url: string; at: string }[]
  fundamentals: {
    available: boolean
    revenue_growth_pct: number | null
    net_income_growth_pct: number | null
    profitable: boolean | null
    dilution_pct: number | null
  }
  fundamental_notes: string[]
}

function ago(iso: string) {
  const h = (Date.now() - new Date(iso).getTime()) / 3_600_000
  if (h < 1) return `${Math.max(1, Math.round(h * 60))}m`
  if (h < 48) return `${Math.round(h)}h`
  return `${Math.round(h / 24)}d`
}

function signed(n: number | null, digits = 1) {
  if (n == null) return '—'
  return `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(digits)}%`
}

// Past this, "last report" is almost certainly a stale data source rather
// than a company that stopped reporting — say so instead of trusting it.
const STALE_DAYS = 120

export function ResearchPanel({ ticker }: { ticker: string }) {
  const { user } = useSession()
  const enabled = !!user
  const opts = { enabled, staleTime: 5 * 60_000, retry: 0 }

  const forecast = useQuery({ queryKey: ['forecast', ticker], queryFn: () => api.get<Forecast>(`/api/forecast/${ticker}`), ...opts })
  const earnings = useQuery({ queryKey: ['earnings', ticker], queryFn: () => api.get<Earnings>(`/api/earnings/${ticker}`), ...opts })
  const research = useQuery({ queryKey: ['research', ticker], queryFn: () => api.get<Research>(`/api/research/${ticker}`), ...opts })

  if (!enabled) {
    return (
      <SignUpGate className="rp-signin" text={`Create a free account to see the earnings forecast, fundamentals and news for ${ticker}.`} />
    )
  }

  const e = earnings.data
  const f = forecast.data
  const r = research.data
  const stale = (e?.last?.days_ago ?? 0) > STALE_DAYS

  return (
    <div className="rp">
      <section className="card">
        <header className="card-head">
          <div>
            <h2 className="card-title">Earnings</h2>
            <p className="card-desc">Dates and Paula’s pre-report read</p>
          </div>
        </header>
        <div className="card-body">
        {earnings.isPending || forecast.isPending ? (
          <p className="rp-note">Loading…</p>
        ) : (
          <>
            <dl className="rp-facts">
              <div>
                <dt>Next report</dt>
                <dd>
                  {e?.next?.date_str ?? 'Not scheduled'}
                  {e?.next?.days_away != null && <span className="rp-dim"> · in {e.next.days_away}d</span>}
                </dd>
              </div>
              <div>
                <dt>Last report</dt>
                <dd>
                  {e?.last?.date_str ?? '—'}
                  {e?.last?.surprise_pct != null && (
                    <span className={e.last.surprise_pct >= 0 ? 'positive' : 'negative'}> · {signed(e.last.surprise_pct)} surprise</span>
                  )}
                </dd>
              </div>
              {f?.lean && (
                <div>
                  <dt>Forecast</dt>
                  <dd>
                    {f.lean}
                    {f.stock_lean && <span className="rp-dim"> · stock: {f.stock_lean}</span>}
                  </dd>
                </div>
              )}
            </dl>
            {stale && (
              <p className="note-warn rp-warn">
                The earnings source hasn't updated since {e?.last?.date_str} — treat this section as out of date.
              </p>
            )}
            {e?.blocked && <p className="note-warn rp-warn">{e.block_reason}</p>}
            {f?.evidence && f.evidence.length > 0 && (
              <ul className="rp-evidence">
                {f.evidence.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
          </>
        )}
        </div>
      </section>

      <section className="card">
        <header className="card-head">
          <div>
            <h2 className="card-title">Fundamentals</h2>
            <p className="card-desc">From SEC filings</p>
          </div>
        </header>
        <div className="card-body">
        {research.isPending ? (
          <p className="rp-note">Loading…</p>
        ) : r?.fundamentals.available ? (
          <dl className="rp-facts">
            <div>
              <dt>Revenue growth</dt>
              <dd className="mono">{signed(r.fundamentals.revenue_growth_pct)}</dd>
            </div>
            <div>
              <dt>Net income growth</dt>
              <dd className="mono">{signed(r.fundamentals.net_income_growth_pct)}</dd>
            </div>
            <div>
              <dt>Profitable</dt>
              <dd>{r.fundamentals.profitable == null ? '—' : r.fundamentals.profitable ? 'Yes' : 'No'}</dd>
            </div>
            <div>
              <dt>Share dilution</dt>
              <dd className="mono">{signed(r.fundamentals.dilution_pct)}</dd>
            </div>
          </dl>
        ) : (
          <p className="rp-note">{r?.fundamental_notes[0] ?? 'Not available.'}</p>
        )}
        </div>
      </section>

      <section className="card rp-news-card">
        <header className="card-head">
          <div>
            <h2 className="card-title">News</h2>
            <p className="card-desc">Latest headlines</p>
          </div>
        </header>
        <div className="card-body">
        {research.isPending ? (
          <p className="rp-note">Loading…</p>
        ) : research.error ? (
          <p className="rp-note">{research.error.message}</p>
        ) : !r?.news.length ? (
          <p className="rp-note">No recent headlines.</p>
        ) : (
          <ul className="rp-news">
            {r.news.map((n) => (
              <li key={n.url || n.headline}>
                {/^https?:\/\//i.test(n.url) ? (
                  <a href={n.url} target="_blank" rel="noreferrer noopener">
                    {n.headline}
                  </a>
                ) : (
                  <span>{n.headline}</span>
                )}
                <span className="rp-dim mono">
                  {n.source} · {ago(n.at)}
                </span>
              </li>
            ))}
          </ul>
        )}
        </div>
      </section>
    </div>
  )
}
