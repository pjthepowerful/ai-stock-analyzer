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
              setMessages(prev => [...prev, { role: 'assistant', content: '**Autopilot Scan**\n\n' + data.log.join('\n\n'), type: 'autopilot' }])
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

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const sendMessage = async (msg) => {
    if (!msg || sending) return
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setInput('')
    setSending(true)
    try {
      const res = await fetch(API + '/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }) })
      const data = await res.json()
      if (data.ok) {
        setMessages(prev => [...prev, { role: 'assistant', content: data.message, type: data.type, ticker: data.ticker || null, signal: data.trade_signal || null }])
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
  const toggleAutopilot = () => sendMessage(autopilot ? 'stop' : 'autopilot')
  const quickAction = (text) => { setInput(text); setTimeout(() => inputRef.current?.focus(), 50) }

  const getGreeting = () => { var h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' }
  var pnl = account ? (account.daily_pnl || 0) : 0
  var pnlPct = account ? (account.daily_pnl_pct || 0) : 0
  var totalUnrealized = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0)

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className={'side' + (sidebarOpen ? '' : ' side-min')}>
        <div className="side-top">
          <div className="side-logo" onClick={() => !sidebarOpen && setSidebarOpen(true)} style={sidebarOpen ? {} : {cursor:'pointer'}}>
            <div className="p-icon">P</div>
            {sidebarOpen && <div><div className="p-name">Paula</div><div className="p-time">{time || '...'}</div></div>}
          </div>
          {sidebarOpen && <button className="side-x" onClick={() => setSidebarOpen(false)}>✕</button>}
        </div>
        {sidebarOpen && <>
          <div className="side-sec">
            {account ? <div className="stats">
              <div className="st"><div className="st-l">Equity</div><div className="st-v">{'$'+account.equity.toLocaleString(undefined,{minimumFractionDigits:2})}</div></div>
              <div className={'st '+(pnl>=0?'st-up':'st-dn')}><div className="st-l">Day P&L</div><div className="st-v">{(pnl>=0?'+':'')+pnl.toFixed(2)}<span className="st-pct">{' ('+pnlPct.toFixed(1)+'%)'}</span></div></div>
              <div className="st"><div className="st-l">Buying Power</div><div className="st-v">{'$'+account.buying_power.toLocaleString(undefined,{minimumFractionDigits:0})}</div></div>
              <div className="st"><div className="st-l">SPY</div><div className={'st-v '+(spyTrend&&spyTrend.change_pct>=0?'up':'dn')}>{spyTrend?(spyTrend.change_pct>=0?'+':'')+spyTrend.change_pct+'%':'—'}</div></div>
            </div> : <div className="st-v shim">Loading...</div>}
          </div>
          <div className="side-sec">
            <button className={'ap-btn'+(autopilot?' ap-on':'')} onClick={toggleAutopilot}>
              <span className={'ap-d'+(autopilot?' ap-d-on':'')}></span>{autopilot?'Autopilot Running':'Start Autopilot'}
            </button>
          </div>
          <div className="side-sec side-fill">
            <div className="sec-h">Positions <span className="cnt">{positions.length}</span>
              {positions.length>0&&<span className={'ptotal '+(totalUnrealized>=0?'up':'dn')}>{(totalUnrealized>=0?'+':'')+totalUnrealized.toFixed(0)}</span>}
            </div>
          </div>
          <div className="side-bot"><div className={'con '+(connected?'con-on':'')}>
            <span className="con-d"></span>{connected?'Connected':'Disconnected'}
          </div></div>
        </>}
      </aside>

      {/* Main */}
      <main className="main">
        {/* Position bar */}
        {positions.length>0&&<div className="posbar">
          <div className="chips">{positions.map((p,i)=>(
            <button key={i} className={'chip '+(p.unrealized_pnl>=0?'c-up':'c-dn')+(selectedPos===p.ticker?' c-sel':'')}
              onClick={()=>setSelectedPos(selectedPos===p.ticker?null:p.ticker)}>
              <span className="c-tk">{p.ticker}</span><span className="c-pnl">{(p.unrealized_pnl_pct>=0?'+':'')+p.unrealized_pnl_pct.toFixed(1)+'%'}</span>
            </button>))}
          </div>
          {selectedPos&&(()=>{var p=positions.find(x=>x.ticker===selectedPos);if(!p)return null;return(
            <div className="pos-expand">
              <div className="pos-info">
                <div className="pos-head"><span className="pos-tk">{p.ticker}</span>
                  <span className={'pos-pl '+(p.unrealized_pnl>=0?'up':'dn')}>{(p.unrealized_pnl>=0?'+':'-')+'$'+Math.abs(p.unrealized_pnl).toFixed(2)+' ('+(p.unrealized_pnl_pct>=0?'+':'')+p.unrealized_pnl_pct.toFixed(2)+'%)'}</span>
                </div>
                <div className="pos-meta">{Math.abs(p.qty)+' shares · $'+(p.avg_entry_price||0).toFixed(2)+' avg · $'+(p.current_price||0).toFixed(2)+' now · '+(p.side==='short'?'SHORT':'LONG')}</div>
                <div className="pos-acts">
                  <button className="act act-a" onClick={()=>{sendMessage(p.ticker);setSelectedPos(null)}}>Analyze</button>
                  <button className="act act-b" onClick={()=>{sendMessage('buy 1 '+p.ticker);setSelectedPos(null)}}>Buy More</button>
                  <button className="act act-s" onClick={()=>{sendMessage((p.side==='short'?'cover ':'sell ')+p.ticker);setSelectedPos(null)}}>{p.side==='short'?'Cover':'Sell All'}</button>
                </div>
              </div>
              <div className="pos-chart"><Chart ticker={p.ticker} signal={null} height={180}/></div>
            </div>
          )})()}
        </div>}

        {/* Chat */}
        <div className="chat">
          {messages.length===0&&!sending&&(
            <div className="welcome">
              <div className="w-logo">P</div>
              <h2>{getGreeting()}</h2>
              <p className="w-sub">What would you like to know?</p>
              <div className="w-grid">
                {[['📊','Analyze a stock','Full signal breakdown','Analyze NVDA'],['🔥','Top gainers','What\'s moving today','top gainers'],['📋','Daily recap','Review today\'s trades','How did we do today?'],['🌍','Market health','SPY, VIX, regime','market regime']].map(([icon,title,desc,cmd],i)=>(
                  <button key={i} className="w-card" onClick={()=>quickAction(cmd)}>
                    <span className="w-icon">{icon}</span><div><span className="w-t">{title}</span><span className="w-d">{desc}</span></div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m,i)=>(
            <div key={i} className={'m m-'+m.role}>
              {m.role==='assistant'?(
                <div className="m-row-ai">
                  <div className="m-av"><div className="av">P</div></div>
                  <div className="m-ai-wrap">
                    <div className="m-ai-text" dangerouslySetInnerHTML={{__html:formatMessage(m.content)}}/>
                    {m.ticker&&<div className="m-chart"><Chart ticker={m.ticker} signal={m.signal} height={240}/></div>}
                  </div>
                </div>
              ):(
                <div className="m-row-user">
                  <div className="m-user-bubble">{m.content}</div>
                </div>
              )}
            </div>
          ))}

          {sending&&(
            <div className="m m-assistant">
              <div className="m-row-ai">
                <div className="m-av"><div className="av">P</div></div>
                <div className="m-ai-wrap"><div className="dots"><span/><span/><span/></div></div>
              </div>
            </div>
          )}
          <div ref={messagesEnd}/>
        </div>

        {/* Input */}
        <div className="inp-area">
          <div className="inp-box">
            <input ref={inputRef} value={input} onChange={e=>setInput(e.target.value)}
              onKeyDown={e=>{if(e.key==='Enter')send()}}
              placeholder="Message Paula..." disabled={sending}/>
            <button className="inp-send" onClick={send} disabled={sending}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

function formatMessage(t){if(!t)return '';return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`(.+?)`/g,'<code>$1</code>').replace(/\n/g,'<br/>')}
export default App
