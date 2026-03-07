import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

const API = 'http://127.0.0.1:3141'
const WS_URL = 'ws://127.0.0.1:3141/ws'

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

  const messagesEnd = useRef(null)
  const wsRef = useRef(null)
  const inputRef = useRef(null)

  // ── WebSocket ──
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        setTimeout(connect, 3000) // reconnect
      }
      ws.onmessage = (e) => {
        const { event, data } = JSON.parse(e.data)
        if (event === 'connected') {
          setAutopilot(data.autopilot)
        }
        if (event === 'chat') {
          setMessages(prev => [...prev, data])
        }
        if (event === 'autopilot') {
          if (data.status === 'started') setAutopilot(true)
          if (data.status === 'stopped') setAutopilot(false)
          if (data.log) {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: `**🟢 Autopilot Scan**\n\n${data.log.join('\n\n')}`,
              type: 'autopilot'
            }])
          }
        }
        if (event === 'trade') {
          refreshData()
        }
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  // ── Refresh data ──
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
    } catch (e) { /* backend not ready */ }
  }, [])

  useEffect(() => {
    refreshData()
    const interval = setInterval(refreshData, 15000) // every 15s
    return () => clearInterval(interval)
  }, [refreshData])

  // ── Auto-scroll ──
  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Send message ──
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
        setMessages(prev => [...prev, { role: 'assistant', content: data.message, type: data.type }])
      } else {
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

  const pnl = account ? (account.equity - (account.last_equity || account.equity)) : 0
  const pnlPct = account?.equity ? (pnl / account.equity * 100) : 0

  return (
    <div className="app">
      {/* ── Top Bar ── */}
      <header className="topbar">
        <div className="topbar-left">
          <div className="logo">P</div>
          <div>
            <h1>Paula</h1>
            <span className="subtitle">{time || '...'} · intraday long/short</span>
          </div>
        </div>
        <div className="topbar-right">
          <div className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          <button
            className={`ap-btn ${autopilot ? 'ap-on' : 'ap-off'}`}
            onClick={toggleAutopilot}
          >
            {autopilot ? '◉ Autopilot ON' : '○ Autopilot OFF'}
          </button>
        </div>
      </header>

      {/* ── Dashboard Strip ── */}
      {account && (
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
                {spyTrend.above_vwap ? ' ▲VWAP' : ' ▼VWAP'}
              </span>
            </div>
          )}
        </div>
      )}

      {/* ── Positions ── */}
      {positions.length > 0 && (
        <div className="positions-strip">
          {positions.map((p, i) => (
            <div key={i} className={`pos-chip ${p.unrealized_pnl >= 0 ? 'pos-green' : 'pos-red'}`}>
              <span className="pos-ticker">{p.side === 'short' ? '🔴' : ''}{p.ticker}</span>
              <span className="pos-pnl">{p.unrealized_pnl_pct >= 0 ? '+' : ''}{p.unrealized_pnl_pct.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Chat ── */}
      <div className="chat">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            <div className="msg-content" dangerouslySetInnerHTML={{ __html: formatMessage(m.content) }} />
          </div>
        ))}
        <div ref={messagesEnd} />
      </div>

      {/* ── Input ── */}
      <div className="input-bar">
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="NVDA… buy 10 AAPL… short TSLA… autopilot…"
          disabled={sending}
        />
        <button onClick={send} disabled={sending}>↑</button>
      </div>
    </div>
  )
}

// ── Simple markdown-ish formatting ──
function formatMessage(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}

export default App
