import { useState, useEffect, useRef, useCallback } from 'react'
import Chart from './Chart'
import { playBuy, playSell, playNotify, playAlert, playProfit, playTick } from './sounds'
import './App.css'

const BACKEND = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://127.0.0.1:3141' : 'https://scurrilously-inevasible-kailey.ngrok-free.dev')
const API = BACKEND
const WS_PROTOCOL = BACKEND.startsWith('https') ? 'wss:' : 'ws:'
const WS_URL = `${WS_PROTOCOL}//${new URL(BACKEND).host}/ws`

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [account, setAccount] = useState(null)
  const [positions, setPositions] = useState([])
  const [autopilot, setAutopilot] = useState(false)
  const [connected, setConnected] = useState(false)
  const [spyTrend, setSpyTrend] = useState(null)
  const [time, setTime] = useState('')
  const [positionChart, setPositionChart] = useState(null)
  const [chatChart, setChatChart] = useState(null)
  const [loading, setLoading] = useState(true)

  const messagesEnd = useRef(null)
  const wsRef = useRef(null)
  const inputRef = useRef(null)

  // WebSocket connection
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws
      ws.onopen = () => setConnected(true)
      ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
      ws.onmessage = (e) => {
        try {
          const { event, data } = JSON.parse(e.data)
          if (event === 'connected') setAutopilot(data.autopilot)

          if (event === 'autopilot') {
            setAutopilot(data.status === 'started')
            if (data.log) {
              playNotify()
              setMessages(prev => [...prev, {
                role: 'assistant',
                content: `**Autopilot Scan Complete**\n\n${data.log.join('\n\n')}`,
                type: 'autopilot'
              }])
            }
          }

          if (event === 'trade') {
            if (data.action === 'buy') playBuy()
            else if (data.action === 'sell' || data.action === 'short') playSell()
            else if (data.action === 'cover') playProfit()
            else if (data.action === 'close_all') playAlert()
            refreshData()
          }
        } catch (e) {}
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  // Fetch backend data
  const refreshData = useCallback(async () => {
    try {
      const [accRes, posRes, spyRes, healthRes] = await Promise.all([
        fetch(`${API}/api/account`).then(r => r.json()),
        fetch(`${API}/api/positions`).then(r => r.json()),
        fetch(`${API}/api/spy-trend`).then(r => r.json()),
        fetch(`${API}/api/health`).then(r => r.json()),
      ])
      if (accRes.ok) setAccount(accRes.data)
      if (posRes.ok) setPositions(posRes.data)
      if (spyRes.ok) setSpyTrend(spyRes.data)
      if (healthRes.time_et) setTime(healthRes.time_et)
      setAutopilot(healthRes.autopilot)
      setLoading(false)
    } catch (e) { setLoading(false) }
  }, [])

  useEffect(() => {
    refreshData()
    const interval = setInterval(refreshData, 15000)
    return () => clearInterval(interval)
  }, [refreshData])

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Send chat message
  const send = async () => {
    const msg = input.trim()
    if (!msg || sending) return
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setInput('')
    setSending(true)
    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      })
      const data = await res.json()
      if (data.ok) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message,
          type: data.type,
          ticker: data.ticker || null,
          signal: data.trade_signal || null
        }])
        if (data.ticker) setChatChart({ ticker: data.ticker, signal: data.trade_signal || null })

        if (data.type === 'trade' && data.message?.includes('Bought')) playBuy()
        else if (data.type === 'trade' && (data.message?.includes('Sold') || data.message?.includes('Shorted'))) playSell()
        else if (data.type === 'trade' && data.message?.includes('Covered')) playProfit()
        else playTick()
        if (data.autopilot !== undefined) setAutopilot(data.autopilot)
      } else {
        playAlert()
        setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ ${data.error}` }])
      }
      refreshData()
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Backend not connected' }])
    }
    setSending(false)
    inputRef.current?.focus()
  }

  const toggleAutopilot = async () => {
    const endpoint = autopilot ? 'stop' : 'start'
    await fetch(`${API}/api/autopilot/${endpoint}`, { method: 'POST' })
    setAutopilot(!autopilot)
  }

  const quickAction = (text) => {
    setInput(text)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  const pnl = account ? (account.equity - (account.last_equity || account.equity)) : 0
  const pnlPct = account?.equity ? (pnl / account.equity * 100) : 0

  const greeting = () => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  }

  return (
    <div className="app">
      {/* ── Top Bar ── */}
      <header className="topbar">
        <div className="topbar-left">
          <div className="logo">P</div>
          <div>
            <h1>Paula</h1>
            <span className="subtitle">{time || '...'}</span>
          </div>
        </div>
        <div className="topbar-right">
          <div className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          <button className={`ap-btn ${autopilot ? 'ap-on' : 'ap-off'}`} onClick={toggleAutopilot}>
            {autopilot ? '◉ Autopilot ON' : '○ Autopilot OFF'}
          </button>
        </div>
      </header>

      {/* ── Dashboard ── */}
      {loading ? (
        <div className="dashboard">
          <div className="dash-item"><span className="dash-label">Loading</span><span className="dash-value shimmer">···</span></div>
        </div>
      ) : account ? (
        <div className="dashboard">
          <div className="dash-item">
            <span className="dash-label">Equity</span>
            <span className="dash-value">${account.equity?.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
          </div>
          <div className="dash-item">
            <span className="dash-label">Cash</span>
            <span className="dash-value">${account.cash?.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
          </div>
          <div className="dash-item">
            <span className="dash-label">Day P&L</span>
            <span className={`dash-value ${pnl >= 0 ? 'green' : 'red'}`}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} ({pnlPct.toFixed(2)}%)
            </span>
          </div>
          <div className="dash-item">
            <span className="dash-label">Positions</span>
            <span className="dash-value">{positions.length}</span>
          </div>
          {spyTrend && (
            <div className="dash-item">
              <span className="dash-label">SPY</span>
              <span className={`dash-value ${spyTrend.change_pct >= 0 ? 'green' : 'red'}`}>
                {spyTrend.change_pct >= 0 ? '+' : ''}{spyTrend.change_pct}%
                {spyTrend.above_vwap ? ' ▲V' : ' ▼V'}
              </span>
            </div>
          )}
        </div>
      ) : null}

      {/* ── Positions + Position Chart ── */}
      {positions.length > 0 && (
        <div className="positions-section">
          <div className="positions-strip">
            {positions.map((p, i) => (
              <div key={i}
                className={`pos-chip ${p.unrealized_pnl >= 0 ? 'pos-green' : 'pos-red'} ${positionChart?.ticker === p.ticker ? 'pos-active' : ''}`}
                onClick={() => setPositionChart(positionChart?.ticker === p.ticker ? null : { ticker: p.ticker })}>
                <span className="pos-ticker">{p.side === 'short' ? '↓ ' : ''}{p.ticker}</span>
                <span className="pos-pnl">{p.unrealized_pnl_pct >= 0 ? '+' : ''}{p.unrealized_pnl_pct.toFixed(1)}%</span>
                <span className="pos-dollars">${Math.abs(p.unrealized_pnl).toFixed(0)}</span>
              </div>
            ))}
          </div>
          {positionChart && (
            <div className="position-chart">
              <button className="chart-close" onClick={() => setPositionChart(null)}>✕</button>
              <Chart ticker={positionChart.ticker} signal={null} height={240} />
            </div>
          )}
        </div>
      )}

      {/* ── Analysis Chart (fixed, above chat) ── */}
      {chatChart && (
        <div className="analysis-chart">
          <button className="chart-close" onClick={() => setChatChart(null)}>✕</button>
          <Chart ticker={chatChart.ticker} signal={chatChart.signal} height={240} />
        </div>
      )}

      {/* ── Chat ── */}
      <div className="chat">
        {messages.length === 0 && !sending && (
          <div className="welcome">
            <h2>{greeting()}</h2>
            <p className="welcome-sub">Ask me anything about the market.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            <div className="msg-content" dangerouslySetInnerHTML={{ __html: formatMessage(m.content) }} />
            {m.role === 'assistant' && m.ticker && (
              <div className="msg-chart">
                <Chart ticker={m.ticker} signal={m.signal} height={260} />
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="msg msg-assistant">
            <div className="typing"><span></span><span></span><span></span></div>
          </div>
        )}
        <div ref={messagesEnd} />
      </div>

      {/* ── Input ── */}
      <div className="input-bar">
        <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Ask about any stock, start autopilot, make a trade..." disabled={sending} />
        <button onClick={send} disabled={sending}>↑</button>
      </div>
    </div>
  )
}

// Format markdown-like messages
function formatMessage(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}

export default App
