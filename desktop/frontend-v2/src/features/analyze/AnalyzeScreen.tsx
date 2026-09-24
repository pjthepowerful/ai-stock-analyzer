import { Search } from 'lucide-react'
import { useState } from 'react'
import { Chart } from '../../components/Chart'
import { SignalCard, type AnalyzeData } from '../../components/SignalCard'
import { api, ApiError } from '../../lib/api'
import { ResearchPanel } from './ResearchPanel'
import './analyze.css'

interface AnalyzeApiResponse {
  ok: boolean
  data?: AnalyzeData
}

const QUICK = ['AAPL', 'NVDA', 'MSFT', 'TSLA', 'AMZN', 'META', 'SPY']

export function AnalyzeScreen() {
  const [ticker, setTicker] = useState('')
  const [result, setResult] = useState<AnalyzeData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function lookup(t: string) {
    const clean = t.trim().toUpperCase()
    if (!clean) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.get<AnalyzeApiResponse>(`/api/analyze/${clean}`)
      if (res.ok && res.data) {
        setResult({ ...res.data, ticker: clean })
      } else {
        setError(`No data for ${clean}.`)
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-inner">
        <header className="page-head">
          <div>
            <h1 className="page-title">Analyze</h1>
            <p className="page-sub">Signal, levels, chart and research for any US ticker</p>
          </div>
          <form
            className="analyze-search"
            onSubmit={(e) => {
              e.preventDefault()
              lookup(ticker)
            }}
          >
            <Search size={15} className="analyze-search-icon" />
            <input
              className="input analyze-input"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="Ticker, e.g. NVDA"
              aria-label="Ticker"
              autoFocus
            />
            <button className="btn btn-primary" type="submit" disabled={loading || !ticker.trim()}>
              {loading ? 'Analyzing…' : 'Analyze'}
            </button>
          </form>
        </header>

        {error && <p className="note-warn">{error}</p>}

        {result ? (
          <>
            <div className="analyze-grid">
              <Chart ticker={result.ticker} height={380} />
              <SignalCard data={result} />
            </div>
            <ResearchPanel ticker={result.ticker} />
          </>
        ) : (
          !loading && (
            <section className="card analyze-empty">
              <p className="analyze-empty-title">Pick a ticker to start</p>
              <p className="text-dim">The same signal engine Paula uses in chat, with the full breakdown.</p>
              <div className="analyze-quick">
                {QUICK.map((t) => (
                  <button
                    key={t}
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      setTicker(t)
                      lookup(t)
                    }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </section>
          )
        )}
      </div>
    </div>
  )
}
