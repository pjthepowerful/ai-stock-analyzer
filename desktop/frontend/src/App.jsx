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
  const [selectedPos, setSelectedPos] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showPositions, setShowPositions] = useState(false)

  const messagesEnd = useRef(null)
  const wsRef = useRef(null)
  const inputRef = useRef(null)

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

  const sendMessage = async (msg) => {
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
        setMessages(prev => [...prev, { role: 'assistant', content: 'Error: ' + (data.error || 'Unknown') }])
      }
      refreshData()
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Backend not connected.' }])
    }
    setSending(false)
    inputRef.current?.focus()
  }

  const send = () => sendMessage(input.trim())

  const toggleAutopilot = () => {
    if (autopilot) {
      sendMessage('stop')
    } else {
      sendMessage('autopilot')
    }
  }

  const tradeAction = async (action, ticker) => {
    sendMessage(action + ' ' + ticker)
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
  var totalUnrealized = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0)

  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <aside className={'sidebar' + (sidebarOpen ? '' : ' collapsed')}>
        <div className="sb-header">
          <div className="logo-row" onClick={() => !sidebarOpen && setSidebarOpen(true)} style={sidebarOpen ? {} : {cursor: 'pointer'}}>
            <div className="logo">P</div>
            {sidebarOpen && <div className="logo-info"><span className="logo-name">Paula</span><span className="logo-time">{time || '...'}</span></div>}
          </div>
          {sidebarOpen && <button className="sb-close" onClick={() => setSidebarOpen(false)}>✕</button>}
        </div>

        {sidebarOpen && (
          <>
            <div className="sb-section">
              <div className="sb-label">Account</div>
              {account ? (
                <div className="stat-grid">
                  <div className="stat-card">
                    <span className="sc-label">Equity</span>
                    <span className="sc-val">{'$' + account.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                  </div>
                  <div className={'stat-card ' + (pnl >= 0 ? 'stat-positive' : 'stat-negative')}>
                    <span className="sc-label">Day P&L</span>
                    <span className={'sc-val ' + (pnl >= 0 ? 'green' : 'red')}>{(pnl >= 0 ? '+' : '') + '$' + Math.abs(pnl).toFixed(2)}</span>
                  </div>
                  <div className="stat-card">
                    <span className="sc-label">Buying Power</span>
                    <span className="sc-val">{'$' + account.buying_power.toLocaleString(undefined, {minimumFractionDigits: 0})}</span>
                  </div>
                  <div className="stat-card">
                    <span className="sc-label">SPY</span>
                    <span className={'sc-val ' + (spyTrend && spyTrend.change_pct >= 0 ? 'green' : 'red')}>
                      {spyTrend ? (spyTrend.change_pct >= 0 ? '+' : '') + spyTrend.change_pct + '%' : '—'}
                    </span>
                  </div>
                </div>
              ) : <div className="sc-val shimmer">Loading...</div>}
            </div>

            <div className="sb-section">
              <button className={'ap-btn ' + (autopilot ? 'ap-on' : '')} onClick={toggleAutopilot}>
                <span className={'ap-dot ' + (autopilot ? 'dot-on' : '')}></span>
                {autopilot ? 'Autopilot Running' : 'Start Autopilot'}
              </button>
            </div>

            <div className="sb-section sb-grow">
              <div className="sb-label" onClick={() => setShowPositions(!showPositions)} style={{cursor: 'pointer'}}>
                Positions <span className="badge">{positions.length}</span>
                {positions.length > 0 && <span className={'pos-total ' + (totalUnrealized >= 0 ? 'green' : 'red')}>{(totalUnrealized >= 0 ? '+' : '') + '$' + Math.abs(totalUnrealized).toFixed(0)}</span>}
              </div>
            </div>

            <div className="sb-footer">
              <div className={'conn ' + (connected ? 'conn-on' : '')}>
                <span className="conn-dot"></span>{connected ? 'Connected' : 'Disconnected'}
              </div>
            </div>
          </>
        )}
      </aside>

      {/* ── Main ── */}
      <main className="main">
        {/* Positions Bar */}
        {positions.length > 0 && (
          <div className="positions-bar">
            <div className="pos-chips">
              {positions.map((p, i) => (
                <div key={i}
                  className={'pos-chip ' + (p.unrealized_pnl >= 0 ? 'chip-green' : 'chip-red') + (selectedPos === p.ticker ? ' chip-active' : '')}
                  onClick={() => setSelectedPos(selectedPos === p.ticker ? null : p.ticker)}>
                  <span className="chip-ticker">{p.ticker}</span>
                  <span className="chip-pnl">{(p.unrealized_pnl_pct >= 0 ? '+' : '') + p.unrealized_pnl_pct.toFixed(1) + '%'}</span>
                </div>
              ))}
            </div>
            {selectedPos && (() => {
              var p = positions.find(x => x.ticker === selectedPos)
              if (!p) return null
              return (
                <div className="pos-detail">
                  <div className="pos-detail-info">
                    <div className="pd-header">
                      <span className="pd-ticker">{p.ticker}</span>
                      <span className={'pd-pnl ' + (p.unrealized_pnl >= 0 ? 'green' : 'red')}>
                        {(p.unrealized_pnl >= 0 ? '+' : '') + '$' + Math.abs(p.unrealized_pnl).toFixed(2)}
                        {' (' + (p.unrealized_pnl_pct >= 0 ? '+' : '') + p.unrealized_pnl_pct.toFixed(2) + '%)'}
                      </span>
                    </div>
                    <div className="pd-meta">
                      <span>{p.qty} shares @ ${p.avg_entry_price?.toFixed(2) || '—'}</span>
                      <span>Market: ${p.current_price?.toFixed(2) || '—'}</span>
                      <span>{p.side === 'short' ? 'SHORT' : 'LONG'}</span>
                    </div>
                    <div className="pd-actions">
                      <button className="action-btn action-analyze" onClick={() => { sendMessage(p.ticker); setSelectedPos(null) }}>Analyze</button>
                      <button className="action-btn action-buy" onClick={() => { tradeAction('buy 1', p.ticker); setSelectedPos(null) }}>Buy More</button>
                      {p.side === 'short' ? (
                        <button className="action-btn action-sell" onClick={() => { tradeAction('cover', p.ticker); setSelectedPos(null) }}>Cover</button>
                      ) : (
                        <button className="action-btn action-sell" onClick={() => { tradeAction('sell', p.ticker); setSelectedPos(null) }}>Sell All</button>
                      )}
                    </div>
                  </div>
                  <div className="pos-detail-chart">
                    <Chart ticker={p.ticker} signal={null} height={200} />
                  </div>
                </div>
              )
            })()}
          </div>
        )}

        {/* Chat */}
        <div className="chat">
          {messages.length === 0 && !sending && (
            <div className="welcome">
              <h2>{getGreeting()}</h2>
              <p className="welcome-sub">What would you like to know?</p>
              <div className="welcome-grid">
                <button className="wc" onClick={() => quickAction('Analyze NVDA')}>
                  <span className="wc-icon">📊</span>
                  <div><span className="wc-title">Analyze a stock</span><span className="wc-desc">Full signal breakdown</span></div>
                </button>
                <button className="wc" onClick={() => quickAction('top gainers')}>
                  <span className="wc-icon">🔥</span>
                  <div><span className="wc-title">Top gainers</span><span className="wc-desc">What's moving today</span></div>
                </button>
                <button className="wc" onClick={() => quickAction('How did we do today?')}>
                  <span className="wc-icon">📋</span>
                  <div><span className="wc-title">Daily recap</span><span className="wc-desc">Review today's trades</span></div>
                </button>
                <button className="wc" onClick={() => quickAction('market regime')}>
                  <span className="wc-icon">🌍</span>
                  <div><span className="wc-title">Market health</span><span className="wc-desc">SPY, VIX, regime</span></div>
                </button>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={'msg msg-' + m.role}>
              {m.role === 'assistant' && <div className="msg-av"><div className="av-p">P</div></div>}
              <div className="msg-body">
                {m.role === 'user' && <div className="msg-label">You</div>}
                <div className="msg-text" dangerouslySetInnerHTML={{ __html: formatMessage(m.content) }} />
                {m.role === 'assistant' && m.ticker && (
                  <div className="msg-chart">
                    <Chart ticker={m.ticker} signal={m.signal} height={260} />
                  </div>
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="msg msg-assistant">
              <div className="msg-av"><div className="av-p">P</div></div>
              <div className="msg-body"><div className="typing"><span></span><span></span><span></span></div></div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        <div className="input-area">
          <div className="input-wrap">
            <input ref={inputRef} value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') send() }}
              placeholder="Ask anything — analyze, trade, autopilot..."
              disabled={sending} />
            <button className="send-btn" onClick={send} disabled={sending}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>
          </div>
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
