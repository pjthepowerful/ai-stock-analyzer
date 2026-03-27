import { useState, useEffect, useRef, useCallback } from 'react'
import Chart from './Chart'
import { playBuy, playSell, playNotify, playAlert, playProfit, playTick } from './sounds'
import './App.css'

const BACKEND = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://127.0.0.1:3141' : 'https://scurrilously-inevasible-kailey.ngrok-free.dev')
const API = BACKEND
const H = { 'ngrok-skip-browser-warning': '1' }
const f = (url, opts = {}) => fetch(url, { ...opts, headers: { ...H, ...(opts.headers || {}) } })
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
            if (data.log) { playNotify(); setMessages(prev => [...prev, { role: 'assistant', content: '**Autopilot Scan**\n\n' + data.log.join('\n\n'), type: 'autopilot' }]) }
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
        f(API + '/api/account').then(r => r.json()),
        f(API + '/api/positions').then(r => r.json()),
        f(API + '/api/spy-trend').then(r => r.json()),
        f(API + '/api/health').then(r => r.json()),
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
    f(API + '/api/chat/clear', { method: 'POST' }).catch(() => {})
    refreshData()
    const i = setInterval(refreshData, 15000)
    return () => clearInterval(i)
  }, [refreshData])

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const sendMessage = async (msg) => {
    if (!msg || sending) return
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setInput('')
    setSending(true)
    try {
      const res = await f(API + '/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      })
      const data = await res.json()
      if (data.ok) {
        setMessages(prev => [...prev, {
          role: 'assistant', content: data.message, type: data.type,
          ticker: data.ticker || null, signal: data.trade_signal || null,
        }])
        if (data.type === 'trade' && data.message) {
          if (data.message.includes('Bought')) playBuy()
          else if (data.message.includes('Sold') || data.message.includes('Shorted')) playSell()
          else if (data.message.includes('Covered')) playProfit()
        } else playTick()
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
  const toggleAutopilot = () => sendMessage(autopilot ? 'stop' : 'autopilot')
  const quickAction = (t) => { setInput(t); setTimeout(() => inputRef.current?.focus(), 50) }
  const getGreeting = () => { var h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' }

  var pnl = account ? (account.daily_pnl || 0) : 0
  var pnlPct = account ? (account.daily_pnl_pct || 0) : 0
  var totalUnrealized = positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0)

  return (
    <div className="layout">
      {/* ── Sidebar ── */}
      <aside className="side">
        <div className="side-head">
          <div className="brand"><div className="p-icon">P</div><div><div className="p-name">Paula</div><div className="p-time">{time || '...'}</div></div></div>
          <div className={'live-pill ' + (connected ? 'live-on' : '')}><span className="live-dot" />{connected ? 'Live' : 'Off'}</div>
        </div>

        {/* P&L */}
        <div className="pnl-block">
          <div className="pnl-top">
            <span className="pnl-label">Today</span>
            <span className={'pnl-num ' + (pnl >= 0 ? 'up' : 'dn')}>{(pnl >= 0 ? '+' : '') + pnl.toFixed(2)}</span>
          </div>
          <div className="pnl-bar-wrap">
            <div className={'pnl-bar ' + (pnl >= 0 ? 'bar-up' : 'bar-dn')} style={{width: Math.min(100, Math.abs(pnlPct) * 10) + '%'}} />
          </div>
          <div className="pnl-stats">
            <span>Equity <b>{account ? '$' + account.equity.toLocaleString(undefined, {maximumFractionDigits: 0}) : '—'}</b></span>
            <span>Power <b>{account ? '$' + account.buying_power.toLocaleString(undefined, {maximumFractionDigits: 0}) : '—'}</b></span>
            <span>SPY <b className={spyTrend && spyTrend.change_pct >= 0 ? 'up' : 'dn'}>{spyTrend ? (spyTrend.change_pct >= 0 ? '+' : '') + spyTrend.change_pct + '%' : '—'}</b></span>
          </div>
        </div>

        {/* Autopilot */}
        <button className={'ap ' + (autopilot ? 'ap-on' : '')} onClick={toggleAutopilot}>
          <span className={'ap-dot ' + (autopilot ? 'ap-dot-on' : '')} />
          <span className="ap-txt">{autopilot ? 'Autopilot Running' : 'Start Autopilot'}</span>
        </button>

        {/* Positions */}
        <div className="pos-sec">
          <div className="pos-header">
            <span>Positions</span>
            <span className="pos-count">{positions.length}</span>
            {positions.length > 0 && <span className={'pos-sum ' + (totalUnrealized >= 0 ? 'up' : 'dn')}>{(totalUnrealized >= 0 ? '+' : '') + '$' + Math.abs(totalUnrealized).toFixed(0)}</span>}
          </div>
          <div className="pos-scroll">
            {positions.length > 0 ? positions.map((p, i) => (
              <div key={i}
                className={'pos-row ' + (p.unrealized_pnl >= 0 ? 'pr-up' : 'pr-dn') + (selectedPos === p.ticker ? ' pr-sel' : '')}
                onClick={() => setSelectedPos(selectedPos === p.ticker ? null : p.ticker)}>
                <div className="pr-left">
                  <span className="pr-tk">{p.ticker}</span>
                  <span className="pr-info">{Math.abs(p.qty) + ' · ' + (p.side === 'short' ? 'SHORT' : 'LONG')}</span>
                </div>
                <div className="pr-right">
                  <span className="pr-pnl">{(p.unrealized_pnl >= 0 ? '+' : '') + '$' + Math.abs(p.unrealized_pnl).toFixed(0)}</span>
                  <span className="pr-pct">{(p.unrealized_pnl_pct >= 0 ? '+' : '') + p.unrealized_pnl_pct.toFixed(1) + '%'}</span>
                </div>
              </div>
            )) : <div className="no-pos">No open positions</div>}
          </div>
        </div>

        {/* Quick actions */}
        <div className="quick-sec">
          <button className="qk" onClick={() => sendMessage('close all')}>Close All</button>
          <button className="qk" onClick={() => sendMessage('top gainers')}>Gainers</button>
          <button className="qk" onClick={() => sendMessage('top losers')}>Losers</button>
          <button className="qk" onClick={() => sendMessage('How did we do today?')}>Recap</button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        {/* Position detail + chart */}
        {selectedPos && (() => {
          var p = positions.find(x => x.ticker === selectedPos)
          if (!p) return null
          return (
            <div className="detail">
              <div className="det-top">
                <div className="det-left">
                  <span className="det-tk">{p.ticker}</span>
                  <span className={'det-pnl ' + (p.unrealized_pnl >= 0 ? 'up' : 'dn')}>
                    {(p.unrealized_pnl >= 0 ? '+' : '-') + '$' + Math.abs(p.unrealized_pnl).toFixed(2)}
                    {' (' + (p.unrealized_pnl_pct >= 0 ? '+' : '') + p.unrealized_pnl_pct.toFixed(2) + '%)'}
                  </span>
                  <span className="det-meta">{Math.abs(p.qty) + ' @ $' + (p.avg_entry_price || 0).toFixed(2) + ' → $' + (p.current_price || 0).toFixed(2) + ' · ' + (p.side === 'short' ? 'SHORT' : 'LONG')}</span>
                </div>
                <div className="det-acts">
                  <button className="da da-a" onClick={() => { sendMessage(p.ticker); setSelectedPos(null) }}>Analyze</button>
                  <button className="da da-b" onClick={() => { sendMessage('buy 1 ' + p.ticker); setSelectedPos(null) }}>Buy More</button>
                  <button className="da da-s" onClick={() => { sendMessage((p.side === 'short' ? 'cover ' : 'sell ') + p.ticker); setSelectedPos(null) }}>{p.side === 'short' ? 'Cover' : 'Sell'}</button>
                  <button className="det-x" onClick={() => setSelectedPos(null)}>✕</button>
                </div>
              </div>
              <div className="det-chart">
                <Chart ticker={p.ticker} signal={null} height={220} />
              </div>
            </div>
          )
        })()}

        {/* Chat */}
        <div className="chat">
          {messages.length === 0 && !sending && (
            <div className="welcome">
              <div className="w-hero">
                <div className="w-p">P</div>
                <h2>{getGreeting()}</h2>
                <p className="w-sub">I can analyze stocks, manage trades, and run autopilot for you.</p>
              </div>
              <div className="w-actions">
                <div className="w-row">
                  <button className="wa wa-main" onClick={() => quickAction('Analyze ')}>
                    <span className="wa-icon">📊</span>
                    <div className="wa-content">
                      <span className="wa-title">Analyze a Stock</span>
                      <span className="wa-desc">Technical signals, trade plan, news sentiment</span>
                    </div>
                  </button>
                  <button className="wa wa-main" onClick={() => quickAction('top gainers')}>
                    <span className="wa-icon">🔥</span>
                    <div className="wa-content">
                      <span className="wa-title">Top Movers</span>
                      <span className="wa-desc">Biggest gainers and losers right now</span>
                    </div>
                  </button>
                </div>
                <div className="w-pills">
                  <button className="wp" onClick={() => sendMessage('How did we do today?')}>Daily Recap</button>
                  <button className="wp" onClick={() => sendMessage('portfolio')}>My Portfolio</button>
                  <button className="wp" onClick={() => sendMessage('What should I buy?')}>Trade Ideas</button>
                  <button className="wp" onClick={() => sendMessage('top losers')}>Top Losers</button>
                </div>
              </div>
              {account && (
                <div className="w-summary">
                  <span>Portfolio: <b>${account.equity.toLocaleString(undefined,{maximumFractionDigits:0})}</b></span>
                  <span className="w-dot">·</span>
                  <span>Today: <b className={pnl >= 0 ? 'up' : 'dn'}>{(pnl >= 0 ? '+' : '') + '$' + Math.abs(pnl).toFixed(0)}</b></span>
                  <span className="w-dot">·</span>
                  <span>Positions: <b>{positions.length}</b></span>
                  {spyTrend && <>
                    <span className="w-dot">·</span>
                    <span>SPY: <b className={spyTrend.change_pct >= 0 ? 'up' : 'dn'}>{(spyTrend.change_pct >= 0 ? '+' : '') + spyTrend.change_pct + '%'}</b></span>
                  </>}
                </div>
              )}
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={'m m-' + m.role}>
              {m.role === 'assistant' ? (
                <div className="mai">
                  <div className="mai-av"><div className="av">P</div></div>
                  <div className="mai-body">
                    <div className="mai-txt" dangerouslySetInnerHTML={{ __html: fmt(m.content) }} />
                    {m.ticker && <div className="mai-chart"><Chart ticker={m.ticker} signal={m.signal} height={240} /></div>}
                  </div>
                </div>
              ) : (
                <div className="mu"><div className="mu-b">{m.content}</div></div>
              )}
            </div>
          ))}

          {sending && <div className="m"><div className="mai"><div className="mai-av"><div className="av">P</div></div><div className="mai-body"><div className="dots"><span /><span /><span /></div></div></div></div>}
          <div ref={messagesEnd} />
        </div>

        <div className="inp-area"><div className="inp-box">
          <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') send() }}
            placeholder="Message Paula..." disabled={sending} />
          <button className="inp-send" onClick={send} disabled={sending}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
          </button>
        </div></div>
      </main>
    </div>
  )
}

function fmt(t) { if (!t) return ''; return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(.+?)`/g, '<code>$1</code>').replace(/\n/g, '<br/>') }
export default App
