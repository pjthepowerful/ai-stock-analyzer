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
  const [toasts, setToasts] = useState([])
  const [view, setView] = useState('chat') // 'chat' or 'dashboard'
  const [perf, setPerf] = useState(null)
  const [sideOpen, setSideOpen] = useState(window.innerWidth > 768)

  const messagesEnd = useRef(null)
  const wsRef = useRef(null)
  const inputRef = useRef(null)
  const toastId = useRef(0)

  // Toast helper
  const addToast = useCallback((msg, type = 'info') => {
    const id = ++toastId.current
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }, [])

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
            if (data.status === 'started') { setAutopilot(true); addToast('Autopilot activated', 'buy') }
            if (data.status === 'stopped') { setAutopilot(false); addToast('Autopilot deactivated', 'sell') }
            if (data.log) {
              playNotify()
              setMessages(prev => [...prev, { role: 'assistant', content: '**Autopilot Scan**\n\n' + data.log.join('\n\n'), type: 'autopilot' }])
            }
          }
          if (event === 'trade') {
            const act = data.action
            const ticker = data.ticker || data.symbol || '???'
            if (act === 'buy') { playBuy(); addToast(`Bought ${ticker}`, 'buy') }
            else if (act === 'sell') { playSell(); addToast(`Sold ${ticker}`, 'sell') }
            else if (act === 'short') { playSell(); addToast(`Shorted ${ticker}`, 'sell') }
            else if (act === 'cover') { playProfit(); addToast(`Covered ${ticker}`, 'buy') }
            else if (act === 'close_all') { playAlert(); addToast('All positions closed', 'warn') }
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
    const i = setInterval(refreshData, 5000)
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
          if (data.message.includes('Bought')) { playBuy(); addToast(data.message.slice(0, 60), 'buy') }
          else if (data.message.includes('Sold') || data.message.includes('Shorted')) { playSell(); addToast(data.message.slice(0, 60), 'sell') }
          else if (data.message.includes('Covered')) { playProfit(); addToast(data.message.slice(0, 60), 'buy') }
          else if (data.message.includes('closed')) { addToast(data.message.slice(0, 60), 'warn') }
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
  const loadDashboard = async () => {
    try {
      const res = await f(API + '/api/performance').then(r => r.json())
      if (res.ok) setPerf(res)
    } catch (e) {}
  }
  const quickAction = (t) => { setInput(t); setTimeout(() => inputRef.current?.focus(), 50) }
  const getGreeting = () => { var h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' }

  var pnl = account ? (account.daily_pnl || 0) : 0
  var pnlPct = account ? (account.daily_pnl_pct || 0) : 0
  var totalUnrealized = positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0)

  return (
    <div className="layout">
      {/* Toast notifications */}
      <div className="toast-wrap">
        {toasts.map(t => (
          <div key={t.id} className={'toast toast-' + t.type}>
            <span className="toast-dot" />
            <span className="toast-msg">{t.msg.replace(/\*\*/g, '')}</span>
            <button className="toast-x" onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))}>✕</button>
          </div>
        ))}
      </div>

      {/* Sidebar */}
      <aside className={'side' + (sideOpen ? '' : ' side-hidden')}>
        <div className="side-head">
          <div className="brand"><div className="p-icon">P</div><div><div className="p-name">Paula</div></div></div>
          <button className="side-close" onClick={() => setSideOpen(false)}>✕</button>
        </div>

        {/* View switcher */}
        <div className="view-sw">
          <button className={'vsw' + (view === 'chat' ? ' vsw-on' : '')} onClick={() => setView('chat')}>Chat</button>
          <button className={'vsw' + (view === 'dashboard' ? ' vsw-on' : '')} onClick={() => { setView('dashboard'); loadDashboard() }}>Dashboard</button>
        </div>

        {/* P&L */}
        <div className="pnl-block">
          <div className="pnl-top">
            <span className="pnl-label">Today</span>
            <span className={'pnl-num ' + (pnl >= 0 ? 'up' : 'dn')}>{(pnl >= 0 ? '+' : '') + pnl.toFixed(2)}</span>
          </div>
          <div className="pnl-bar-wrap"><div className={'pnl-bar ' + (pnl >= 0 ? 'bar-up' : 'bar-dn')} style={{width: Math.min(100, Math.abs(pnlPct) * 10) + '%'}} /></div>
          <div className="pnl-stats">
            <span>Equity <b className={pnl >= 0 ? 'up' : 'dn'}>{account ? '$' + account.equity.toLocaleString(undefined, {maximumFractionDigits: 0}) : '—'}</b></span>
            <span>Day <b className={pnlPct >= 0 ? 'up' : 'dn'}>{(pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(2) + '%'}</b></span>
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
                  <span className="pr-info">{Math.abs(p.qty) + ' · ' + (p.side === 'short' ? 'SHORT' : 'LONG')}{p.stop_loss ? ' · SL $' + p.stop_loss : ''}</span>
                </div>
                <div className="pr-right">
                  <span className="pr-pnl">{(p.unrealized_pnl >= 0 ? '+' : '') + '$' + Math.abs(p.unrealized_pnl).toFixed(0)}</span>
                  <span className="pr-pct">{(p.unrealized_pnl_pct >= 0 ? '+' : '') + p.unrealized_pnl_pct.toFixed(1) + '%'}</span>
                </div>
              </div>
            )) : <div className="no-pos">No open positions</div>}
          </div>
        </div>

      </aside>

      {/* Main */}
      <main className="main">
        {/* Mobile hamburger */}
        {!sideOpen && <button className="hamburger" onClick={() => setSideOpen(true)}>☰</button>}

        {view === 'dashboard' ? (
          /* ── Dashboard View ── */
          <div className="dash">
            <h2 className="dash-title">Performance</h2>
            {perf ? (
              <div className="dash-grid">
                {/* Equity Curve */}
                {perf.pnl_history && perf.pnl_history.length > 1 && (
                  <div className="dash-card dc-wide">
                    <span className="dc-label">Equity Curve</span>
                    <EquityChart data={perf.pnl_history} />
                  </div>
                )}
                <div className="dash-card">
                  <span className="dc-label">Total Trades</span>
                  <span className="dc-val">{perf.total_trades}</span>
                </div>
                <div className="dash-card">
                  <span className="dc-label">Current Params</span>
                  <div className="dc-params">
                    {perf.current_params && Object.entries(perf.current_params).map(([k, v]) => (
                      <div key={k} className="dc-param"><span>{k}</span><span>{typeof v === 'number' ? (v < 1 && v > 0 ? (v * 100).toFixed(1) + '%' : v) : String(v)}</span></div>
                    ))}
                  </div>
                </div>
                <div className="dash-card dc-wide">
                  <span className="dc-label">Auto-Tune History</span>
                  <div className="dc-history">
                    {perf.tune_history && perf.tune_history.length > 0 ? perf.tune_history.slice().reverse().map((h, i) => (
                      <div key={i} className="dc-tune">
                        <span className="dc-date">{h.date}</span>
                        <span className={'dc-pnl ' + ((h.stats?.pnl || 0) >= 0 ? 'up' : 'dn')}>{(h.stats?.pnl >= 0 ? '+' : '') + '$' + Math.abs(h.stats?.pnl || 0).toFixed(0)}</span>
                        <span className="dc-wr">{h.stats?.wins}W/{h.stats?.losses}L</span>
                        <div className="dc-changes">{h.changes?.map((c, j) => <div key={j}>{c}</div>)}</div>
                      </div>
                    )) : <div className="no-pos">No tune history yet</div>}
                  </div>
                </div>
                <div className="dash-card dc-wide">
                  <span className="dc-label">Recent Trades</span>
                  <div className="dc-trades">
                    {perf.recent_trades && perf.recent_trades.length > 0 ? perf.recent_trades.slice().reverse().map((t, i) => (
                      <div key={i} className="dc-trade">
                        <span className={'dc-action ' + (t.action === 'buy' ? 'up' : 'dn')}>{t.action?.toUpperCase()}</span>
                        <span className="dc-ticker">{t.ticker}</span>
                        <span className="dc-time">{t.time?.slice(11, 16)}</span>
                      </div>
                    )) : <div className="no-pos">No trades logged yet</div>}
                  </div>
                </div>
              </div>
            ) : <div className="no-pos">Loading dashboard...</div>}
          </div>
        ) : (
          /* ── Chat View ── */
          <>
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
                  <span className="det-meta">{Math.abs(p.qty) + ' @ $' + (p.avg_entry || 0).toFixed(2) + ' → $' + (p.current_price || 0).toFixed(2) + ' · ' + (p.side === 'short' ? 'SHORT' : 'LONG')}{p.stop_loss ? ' · Stop: $' + p.stop_loss : ''}</span>
                </div>
                <div className="det-acts">
                  <button className="da da-a" onClick={() => { sendMessage(p.ticker); setSelectedPos(null) }}>Analyze</button>
                  <button className="da da-b" onClick={() => { sendMessage('buy 1 ' + p.ticker); setSelectedPos(null) }}>Buy More</button>
                  <button className="da da-s" onClick={() => { sendMessage((p.side === 'short' ? 'cover ' : 'sell ') + p.ticker); setSelectedPos(null) }}>{p.side === 'short' ? 'Cover' : 'Sell'}</button>
                  <button className="det-x" onClick={() => setSelectedPos(null)}>✕</button>
                </div>
              </div>
              <div className="det-chart"><Chart ticker={p.ticker} signal={null} height={220} /></div>
            </div>
          )
        })()}

        <div className="chat">
          {messages.length === 0 && !sending && (
            <div className="welcome">
              <div className="w-text">
                <h1>{(() => {
                  var h = new Date().getHours()
                  if (h < 12) return <><span className="w-gr">Good morning,</span> PJ</>
                  if (h < 17) return <><span className="w-gr">Good afternoon,</span> PJ</>
                  return <><span className="w-gr">Good evening,</span> PJ</>
                })()}</h1>
              </div>
              <div className="w-prompts">
                <button className="wp" onClick={() => sendMessage('market regime')}>Analyze the market</button>
                <button className="wp" onClick={() => sendMessage('top gainers')}>Trending tickers</button>
                <button className="wp" onClick={() => sendMessage('How did we do today?')}>Recap trades</button>
                <button className="wp" onClick={() => sendMessage('What should I buy?')}>Trade ideas</button>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={'m m-' + m.role}>
              {m.role === 'assistant' ? (
                <div className="mai"><div className="mai-av"><div className="av">P</div></div>
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
          </>
        )}
      </main>
    </div>
  )
}

function EquityChart({ data }) {
  if (!data || data.length < 2) return null
  const vals = data.map(d => d.equity || d.value || 0).filter(v => v > 0)
  if (vals.length < 2) return null
  const min = Math.min(...vals), max = Math.max(...vals)
  const range = max - min || 1
  const w = 500, h = 120, pad = 20
  const points = vals.map((v, i) => {
    const x = pad + (i / (vals.length - 1)) * (w - pad * 2)
    const y = pad + (1 - (v - min) / range) * (h - pad * 2)
    return `${x},${y}`
  }).join(' ')
  const isUp = vals[vals.length - 1] >= vals[0]
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{width:'100%',height:'auto'}}>
      <defs><linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={isUp ? '#00dda0' : '#f04060'} stopOpacity="0.2"/>
        <stop offset="100%" stopColor={isUp ? '#00dda0' : '#f04060'} stopOpacity="0"/>
      </linearGradient></defs>
      <polygon points={`${pad},${h - pad} ${points} ${w - pad},${h - pad}`} fill="url(#eq)" />
      <polyline points={points} fill="none" stroke={isUp ? '#00dda0' : '#f04060'} strokeWidth="2" />
      <text x={pad} y={h - 4} fill="#4d4d66" fontSize="9" fontFamily="JetBrains Mono">${vals[0].toLocaleString(undefined,{maximumFractionDigits:0})}</text>
      <text x={w - pad} y={h - 4} fill={isUp ? '#00dda0' : '#f04060'} fontSize="9" fontFamily="JetBrains Mono" textAnchor="end">${vals[vals.length-1].toLocaleString(undefined,{maximumFractionDigits:0})}</text>
    </svg>
  )
}

function fmt(t) { if (!t) return ''; return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(.+?)`/g, '<code>$1</code>').replace(/\n/g, '<br/>') }
export default App
