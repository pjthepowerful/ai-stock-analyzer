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
    <div className="analyze-screen">
      <form
        className="analyze-search"
        onSubmit={(e) => {
          e.preventDefault()
          lookup(ticker)
        }}
      >
        <input
          className="analyze-input"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Enter a ticker — AAPL, TSLA, NVDA…"
          autoFocus
        />
        <button className="analyze-go" type="submit" disabled={loading || !ticker.trim()}>
          {loading ? '…' : 'Analyze →'}
        </button>
      </form>

      {error && <div className="analyze-error">{error}</div>}

      {result && (
        <div className="analyze-result">
          <SignalCard data={result} />
          <Chart ticker={result.ticker} height={340} />
          <ResearchPanel ticker={result.ticker} />
        </div>
      )}

      {!result && !error && !loading && (
        <div className="analyze-empty">Real signal engine, real data — enter any ticker to see the full read.</div>
      )}
    </div>
  )
}
