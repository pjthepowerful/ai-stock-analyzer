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
  const [loading, setLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const messagesEnd = useRef(null)
  const wsRef = useRef(null)
  const inputRef = useRef(null)

  // WebSocket
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
                content: '**Autopilot Scan Complete**\n\n' + data.log.join('\n\n'),
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
        } catch (err) {}
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const refreshData = useCallback(async () => {
    try {
      const [accRes, posRes, spyRes, healthRes] = await Promise.all([
        fetch(API + '/api/account').then(r => r.json()),
        fetch(API + '/api/positions').then(r => r.json()),
        fetch(API + '/api/spy-trend').then(r => r.json()),
        fetch(API + '/api/health').then(r => r.json()),
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
    fetch(API + '/api/chat/clear', { method: 'POST' }).catch(() => {})
    refreshData()
    const interval = setInterval(refreshData, 15000)
    return () => clearInterval(interval)
  }, [refreshData])

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const msg = input.trim()
    if (!msg || sending) return
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setInput('')
    setSending(true)
    try {
      const res = await fetch(API + '/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      })
      const data = await res.json()
      if (data.ok) {
        setMessages(prev => [...prev, {
          role: 'assistant', content: data.message, type: data.type,
          ticker: data.ticker || null, signal: data.trade_signal || null,
        }])
        if (data.type === 'trade' && data.message && data.message.includes('Bought')) playBuy()
        else if (data.type === 'trade' && data.message && (data.message.includes('Sold') || data.message.includes('Shorted'))) playSell()
        else if (data.type === 'trade' && data.message && data.message.includes('Covered')) playProfit()
        else playTick()
        if (data.autopilot !== undefined) setAutopilot(data.autopilot)
      } else {
        playAlert()
        setMessages(prev => [...prev, { role: 'assistant', content: 'Error: ' + (data.error || 'Unknown error') }])
      }
      refreshData()
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Backend not connected.' }])
    }
    setSending(false)
    inputRef.current?.focus()
  }

  const toggleAutopilot = async () => {
    var endpoint = autopilot ? 'stop' : 'start'
    await fetch(API + '/api/autopilot/' + endpoint, { method: 'POST' })
    setAutopilot(!autopilot)
  }

  const quickAction = (text) => {
    setInput(text)
    setTimeout(() => { if (inputRef.current) inputRef.current.focus() }, 50)
  }

  const getGreeting = () => {
    var h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  }

  var pnl = account ? (account.daily_pnl || 0) : 0
  var pnlPct = account ? (account.daily_pnl_pct || 0) : 0

  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <aside className={'sidebar' + (sidebarOpen ? '' : ' sidebar-collapsed')}>
        <div className="sidebar-header">
          <div className="logo-group">
            <div className="logo">P</div>
            <div className="logo-text">
              <span className="logo-name">Paula</span>
              <span className="logo-sub">{time || 'Connecting...'}</span>
            </div>
          </div>
          <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>

        {sidebarOpen && (
          <>
            {/* Account */}
            <div className="sidebar-section">
              <div className="sidebar-label">Account</div>
              {account ? (
                <div className="account-grid">
                  <div className="account-stat">
                    <span className="stat-label">Equity</span>
                    <span className="stat-value">{'$' + account.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                  </div>
                  <div className="account-stat">
                    <span className="stat-label">Day P&L</span>
                    <span className={'stat-value ' + (pnl >= 0 ? 'green' : 'red')}>
                      {(pnl >= 0 ? '+' : '') + '$' + Math.abs(pnl).toFixed(2)}
                      <small>{' (' + (pnl >= 0 ? '+' : '') + pnlPct.toFixed(2) + '%)'}</small>
                    </span>
                  </div>
                  <div className="account-stat">
                    <span className="stat-label">Buying Power</span>
                    <span className="stat-value">{'$' + account.buying_power.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                  </div>
                  {spyTrend && (
                    <div className="account-stat">
                      <span className="stat-label">SPY</span>
                      <span className={'stat-value ' + (spyTrend.change_pct >= 0 ? 'green' : 'red')}>
                        {(spyTrend.change_pct >= 0 ? '+' : '') + spyTrend.change_pct + '%'}
                        {spyTrend.above_vwap ? ' ▲' : ' ▼'}
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="stat-value shimmer">Loading...</div>
              )}
            </div>

            {/* Positions */}
            <div className="sidebar-section">
              <div className="sidebar-label">Positions <span className="badge">{positions.length}</span></div>
              {positions.length > 0 ? (
                <div className="positions-list">
                  {positions.map((p, i) => (
                    <div key={i}
                      className={'pos-row ' + (p.unrealized_pnl >= 0 ? 'pos-green' : 'pos-red') + (positionChart && positionChart.ticker === p.ticker ? ' pos-active' : '')}
                      onClick={() => setPositionChart(positionChart && positionChart.ticker === p.ticker ? null : { ticker: p.ticker })}>
                      <span className="pos-ticker">{(p.side === 'short' ? '↓' : '') + p.ticker}</span>
                      <span className="pos-qty">{p.qty}</span>
                      <span className={'pos-pnl ' + (p.unrealized_pnl >= 0 ? 'green' : 'red')}>
                        {(p.unrealized_pnl_pct >= 0 ? '+' : '') + p.unrealized_pnl_pct.toFixed(1) + '%'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="no-positions">No open positions</div>
              )}
              {positionChart && (
                <div className="sidebar-chart">
                  <Chart ticker={positionChart.ticker} signal={null} height={180} />
                </div>
              )}
            </div>

            {/* Autopilot */}
            <div className="sidebar-section">
              <button className={'autopilot-btn ' + (autopilot ? 'ap-active' : '')} onClick={toggleAutopilot}>
                <span className={'ap-dot ' + (autopilot ? 'ap-dot-on' : '')}></span>
                {autopilot ? 'Autopilot Running' : 'Start Autopilot'}
              </button>
            </div>

            {/* Status */}
            <div className="sidebar-footer">
              <div className={'conn-status ' + (connected ? 'conn-on' : 'conn-off')}>
                <span className="conn-dot"></span>
                {connected ? 'Connected' : 'Disconnected'}
              </div>
            </div>
          </>
        )}
      </aside>

      {/* ── Main Chat ── */}
      <main className="main">
        <div className="chat">
          {messages.length === 0 && !sending && (
            <div className="welcome">
              <h2>{getGreeting()}</h2>
              <p className="welcome-sub">What would you like to know?</p>
              <div className="welcome-grid">
                <button className="welcome-card" onClick={() => quickAction('Analyze NVDA')}>
                  <span className="wc-icon">📊</span>
                  <div>
                    <span className="wc-title">Analyze a stock</span>
                    <span className="wc-desc">Get a full signal breakdown</span>
                  </div>
                </button>
                <button className="welcome-card" onClick={() => quickAction('top gainers')}>
                  <span className="wc-icon">🔥</span>
                  <div>
                    <span className="wc-title">Top gainers</span>
                    <span className="wc-desc">See what's moving today</span>
                  </div>
                </button>
                <button className="welcome-card" onClick={() => quickAction('How did we do today?')}>
                  <span className="wc-icon">📋</span>
                  <div>
                    <span className="wc-title">Daily recap</span>
                    <span className="wc-desc">Review today's trades</span>
                  </div>
                </button>
                <button className="welcome-card" onClick={() => quickAction('market regime')}>
                  <span className="wc-icon">🌍</span>
                  <div>
                    <span className="wc-title">Market health</span>
                    <span className="wc-desc">SPY, VIX, regime check</span>
                  </div>
                </button>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={'msg ' + (m.role === 'user' ? 'msg-user' : 'msg-ai')}>
              {m.role === 'assistant' && (
                <div className="msg-avatar"><div className="avatar-p">P</div></div>
              )}
              <div className={'msg-bubble ' + (m.role === 'user' ? 'bubble-user' : 'bubble-ai')}>
                <div dangerouslySetInnerHTML={{ __html: formatMessage(m.content) }} />
                {m.role === 'assistant' && m.ticker && (
                  <div className="inline-chart">
                    <Chart ticker={m.ticker} signal={m.signal} height={260} />
                  </div>
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="msg msg-ai">
              <div className="msg-avatar"><div className="avatar-p">P</div></div>
              <div className="bubble-ai">
                <div className="typing"><span></span><span></span><span></span></div>
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        {/* Input */}
        <div className="input-area">
          <div className="input-wrap">
            <input ref={inputRef} value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') send() }}
              placeholder="Ask anything — analyze a stock, start autopilot, make a trade..."
              disabled={sending} />
            <button className="send-btn" onClick={send} disabled={sending}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
          <span className="input-hint">Paula can make mistakes. Verify important info.</span>
        </div>
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
