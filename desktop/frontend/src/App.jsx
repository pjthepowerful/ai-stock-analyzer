import { useState, useEffect, useRef, useCallback } from 'react'
import Chart from './Chart'
import { playBuy, playSell, playNotify, playAlert, playProfit, playTick } from './sounds'
import './App.css'

const BACKEND = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://127.0.0.1:3141' : 'https://scurrilously-inevasible-kailey.ngrok-free.dev')
const API = BACKEND
const WS_PROTOCOL = BACKEND.startsWith('https') ? 'wss:' : 'ws:'
const WS_URL = `${WS_PROTOCOL}//${new URL(BACKEND).host}/ws`

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good Morning'
  if (h < 17) return 'Good Afternoon'
  return 'Good Evening'
}

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
  const [activeChart, setActiveChart] = useState(null)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('chat') // 'chat' | 'positions'

  const messagesEnd = useRef(null)
  const wsRef = useRef(null)
  const inputRef = useRef(null)
  const hasMessages = messages.length > 0

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
            if (data.status === 'started') setAutopilot(true)
            if (data.status === 'stopped') setAutopilot(false)
            if (data.log) {
              playNotify()
              setMessages(prev => [...prev, {
                role: 'assistant',
                content: `**🟢 Autopilot Scan**\n\n${data.log.join('\n\n')}`,
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

  const send = async (override) => {
    const msg = (override || input).trim()
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
          role: 'assistant', content: data.message, type: data.type, ticker: data.ticker,
        }])
        if (data.ticker) setActiveChart({ ticker: data.ticker, signal: data.trade_signal || null })
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

  const pnl = account ? (account.equity - (account.last_equity || account.equity)) : 0
  const pnlPct = account?.equity ? (pnl / account.equity * 100) : 0

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <nav className="sidebar">
        <div className="sidebar-top">
          <div className="sidebar-logo">P</div>
          <button className={`sidebar-btn ${view === 'chat' ? 'active' : ''}`} onClick={() => setView('chat')} title="Chat">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </button>
          <button className={`sidebar-btn ${view === 'positions' ? 'active' : ''}`} onClick={() => setView('positions')} title="Positions">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></svg>
          </button>
        </div>
        <div className="sidebar-bottom">
          <div className={`sidebar-dot ${connected ? 'on' : 'off'}`} />
        </div>
      </nav>

      {/* ── Main Content ── */}
      <main className="main">
        {/* ── Top Strip ── */}
        <header className="topstrip">
          {account && (
            <div className="topstrip-stats">
              <span className="stat">${account.equity?.toLocaleString(undefined, {minimumFractionDigits: 0})}</span>
              <span className="stat-divider">·</span>
              <span className={`stat ${pnl >= 0 ? 'green' : 'red'}`}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(0)} today</span>
              <span className="stat-divider">·</span>
              <span className="stat">{positions.length} positions</span>
              {spyTrend && <>
                <span className="stat-divider">·</span>
                <span className={`stat ${spyTrend.change_pct >= 0 ? 'green' : 'red'}`}>SPY {spyTrend.change_pct >= 0 ? '+' : ''}{spyTrend.change_pct}%</span>
              </>}
            </div>
          )}
          <div className="topstrip-right">
            <span className="time-label">{time}</span>
            <button className={`ap-btn ${autopilot ? 'ap-on' : 'ap-off'}`} onClick={toggleAutopilot}>
              {autopilot ? '◉ Autopilot' : '○ Autopilot'}
            </button>
          </div>
        </header>

        {/* ── Chat View ── */}
        {view === 'chat' && (
          <div className="chat-area">
            {!hasMessages && !sending ? (
              <div className="welcome">
                <div className="welcome-orb"></div>
                <h1>{getGreeting()}</h1>
                <p>What's on <span className="accent">your mind?</span></p>

                <div className="welcome-input-wrap">
                  <input
                    ref={inputRef}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && send()}
                    placeholder="Ask about any stock, start autopilot, make a trade..."
                    className="welcome-input"
                    disabled={sending}
                  />
                  <button className="welcome-send" onClick={() => send()} disabled={sending}>↑</button>
                </div>

                <p className="examples-label">GET STARTED WITH AN EXAMPLE</p>
                <div className="examples">
                  <button className="example-card" onClick={() => send('analyze NVDA')}>
                    <span className="example-icon">📊</span>
                    <span className="example-text">Analyze NVDA<br/><small>full signal breakdown</small></span>
                  </button>
                  <button className="example-card" onClick={() => send('top gainers')}>
                    <span className="example-icon">🔥</span>
                    <span className="example-text">Top Gainers<br/><small>today's movers</small></span>
                  </button>
                  <button className="example-card" onClick={() => send('portfolio')}>
                    <span className="example-icon">💼</span>
                    <span className="example-text">My Portfolio<br/><small>positions & P&L</small></span>
                  </button>
                  <button className="example-card" onClick={() => send('autopilot')}>
                    <span className="example-icon">🤖</span>
                    <span className="example-text">Start Autopilot<br/><small>scan & trade automatically</small></span>
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="messages">
                  {messages.map((m, i) => (
                    <div key={i} className={`msg msg-${m.role}`}>
                      {m.role === 'assistant' && <div className="msg-avatar">P</div>}
                      <div className="msg-content" dangerouslySetInnerHTML={{ __html: formatMessage(m.content) }} />
                    </div>
                  ))}
                  {sending && (
                    <div className="msg msg-assistant">
                      <div className="msg-avatar">P</div>
                      <div className="typing"><span></span><span></span><span></span></div>
                    </div>
                  )}
                  <div ref={messagesEnd} />
                </div>

                {activeChart && (
                  <div className="chart-wrapper">
                    <button className="chart-close" onClick={() => setActiveChart(null)}>✕</button>
                    <Chart ticker={activeChart.ticker} signal={activeChart.signal} height={260} />
                  </div>
                )}

                <div className="input-bar">
                  <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && send()}
                    placeholder="Ask Paula anything..." disabled={sending} />
                  <button onClick={() => send()} disabled={sending}>↑</button>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Positions View ── */}
        {view === 'positions' && (
          <div className="positions-view">
            <h2>Open Positions</h2>
            {positions.length === 0 ? (
              <p className="empty-state">No open positions</p>
            ) : (
              <div className="positions-list">
                {positions.map((p, i) => (
                  <div key={i} className={`position-row ${p.unrealized_pnl >= 0 ? 'pos-green' : 'pos-red'}`}
                    onClick={() => { setActiveChart({ ticker: p.ticker, signal: null }); setView('chat') }}>
                    <div className="pos-left">
                      <span className="pos-ticker-lg">{p.ticker}</span>
                      <span className="pos-side">{p.side === 'short' ? 'SHORT' : 'LONG'} · {Math.abs(p.qty)} shares</span>
                    </div>
                    <div className="pos-middle">
                      <span className="pos-entry">Entry ${p.avg_entry?.toFixed(2)}</span>
                      <span className="pos-current">Now ${p.current_price?.toFixed(2)}</span>
                    </div>
                    <div className="pos-right">
                      <span className={`pos-pnl-lg ${p.unrealized_pnl >= 0 ? 'green' : 'red'}`}>
                        {p.unrealized_pnl >= 0 ? '+' : ''}${p.unrealized_pnl?.toFixed(2)}
                      </span>
                      <span className={`pos-pct ${p.unrealized_pnl_pct >= 0 ? 'green' : 'red'}`}>
                        {p.unrealized_pnl_pct >= 0 ? '+' : ''}{p.unrealized_pnl_pct?.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

function formatMessage(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}

export default App
