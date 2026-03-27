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
            if (data.action === 'buy') playBuy(); else if (data.action === 'sell' || data.action === 'short') playSell()
            else if (data.action === 'cover') playProfit(); else if (data.action === 'close_all') playAlert()
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
        fetch(API+'/api/account').then(r=>r.json()), fetch(API+'/api/positions').then(r=>r.json()),
        fetch(API+'/api/spy-trend').then(r=>r.json()), fetch(API+'/api/health').then(r=>r.json()),
      ])
      if (accRes.ok) setAccount(accRes.data); if (posRes.ok) setPositions(posRes.data)
      if (spyRes.ok) setSpyTrend(spyRes.data); if (healthRes.time_et) setTime(healthRes.time_et)
      setAutopilot(healthRes.autopilot); setLoading(false)
    } catch (e) { setLoading(false) }
  }, [])

  useEffect(() => { fetch(API+'/api/chat/clear',{method:'POST'}).catch(()=>{}); refreshData(); const i=setInterval(refreshData,15000); return()=>clearInterval(i) }, [refreshData])
  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const sendMessage = async (msg) => {
    if (!msg || sending) return
    setMessages(prev => [...prev, { role: 'user', content: msg }]); setInput(''); setSending(true)
    try {
      const res = await fetch(API+'/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:msg}) })
      const data = await res.json()
      if (data.ok) {
        setMessages(prev => [...prev, { role:'assistant', content:data.message, type:data.type, ticker:data.ticker||null, signal:data.trade_signal||null }])
        if (data.type==='trade'&&data.message) { if(data.message.includes('Bought'))playBuy(); else if(data.message.includes('Sold')||data.message.includes('Shorted'))playSell(); else if(data.message.includes('Covered'))playProfit() }
        else playTick()
        if (data.autopilot!==undefined) setAutopilot(data.autopilot)
      } else { playAlert(); setMessages(prev=>[...prev,{role:'assistant',content:'Error: '+(data.error||'Unknown')}]) }
      refreshData()
    } catch(e) { setMessages(prev=>[...prev,{role:'assistant',content:'Backend not connected.'}]) }
    setSending(false); inputRef.current?.focus()
  }
  const send = () => sendMessage(input.trim())
  const toggleAutopilot = () => sendMessage(autopilot ? 'stop' : 'autopilot')
  const quickAction = (t) => { setInput(t); setTimeout(()=>inputRef.current?.focus(),50) }
  const getGreeting = () => { var h=new Date().getHours(); return h<12?'Good morning':h<17?'Good afternoon':'Good evening' }

  var pnl = account?(account.daily_pnl||0):0, pnlPct = account?(account.daily_pnl_pct||0):0
  var totalUnrealized = positions.reduce((s,p)=>s+(p.unrealized_pnl||0),0)
  var winners = positions.filter(p=>p.unrealized_pnl>=0).length
  var losers = positions.filter(p=>p.unrealized_pnl<0).length

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="side">
        <div className="side-top">
          <div className="side-logo"><div className="p-icon">P</div><div><div className="p-name">Paula</div><div className="p-time">{time||'...'}</div></div></div>
          <div className={'con-badge '+(connected?'con-on':'')}>
            <span className="con-dot"></span>{connected?'Live':'Offline'}
          </div>
        </div>

        {/* Big P&L hero */}
        <div className="pnl-hero">
          <div className="pnl-label">Today's P&L</div>
          <div className={'pnl-val '+(pnl>=0?'up':'dn')}>
            {(pnl>=0?'+':'-')+'$'+Math.abs(pnl).toFixed(2)}
          </div>
          <div className={'pnl-pct '+(pnl>=0?'up':'dn')}>{(pnlPct>=0?'+':'')+pnlPct.toFixed(2)+'%'}</div>
        </div>

        {/* Stats row */}
        <div className="stats-row">
          <div className="sr"><span className="sr-l">Equity</span><span className="sr-v">{account?'$'+account.equity.toLocaleString(undefined,{maximumFractionDigits:0}):'—'}</span></div>
          <div className="sr"><span className="sr-l">Power</span><span className="sr-v">{account?'$'+account.buying_power.toLocaleString(undefined,{maximumFractionDigits:0}):'—'}</span></div>
          <div className="sr"><span className="sr-l">SPY</span><span className={'sr-v '+(spyTrend&&spyTrend.change_pct>=0?'up':'dn')}>{spyTrend?(spyTrend.change_pct>=0?'+':'')+spyTrend.change_pct+'%':'—'}</span></div>
        </div>

        {/* Autopilot */}
        <div className="side-sec">
          <button className={'ap-btn'+(autopilot?' ap-on':'')} onClick={toggleAutopilot}>
            <span className={'ap-d'+(autopilot?' ap-d-on':'')}></span>
            <div className="ap-info">
              <span className="ap-title">{autopilot?'Autopilot Running':'Start Autopilot'}</span>
              <span className="ap-sub">{autopilot?'Scanning every 5 min':'Click to activate'}</span>
            </div>
          </button>
        </div>

        {/* Positions in sidebar */}
        <div className="side-sec side-pos">
          <div className="sec-h">
            Positions
            {positions.length>0&&<>
              <span className="cnt">{positions.length}</span>
              <span className="win-lose"><span className="up">{winners}W</span> <span className="dn">{losers}L</span></span>
              <span className={'ptotal '+(totalUnrealized>=0?'up':'dn')}>{(totalUnrealized>=0?'+':'-')+'$'+Math.abs(totalUnrealized).toFixed(0)}</span>
            </>}
          </div>
          <div className="pos-list">
            {positions.length>0?positions.map((p,i)=>(
              <div key={i} className={'pos-item '+(p.unrealized_pnl>=0?'pi-up':'pi-dn')+(selectedPos===p.ticker?' pi-sel':'')}
                onClick={()=>setSelectedPos(selectedPos===p.ticker?null:p.ticker)}>
                <div className="pi-left">
                  <span className="pi-tk">{p.ticker}</span>
                  <span className="pi-meta">{Math.abs(p.qty)}sh · {p.side==='short'?'SHORT':'LONG'}</span>
                </div>
                <div className="pi-right">
                  <span className={'pi-pnl '+(p.unrealized_pnl>=0?'up':'dn')}>{(p.unrealized_pnl>=0?'+':'-')+'$'+Math.abs(p.unrealized_pnl).toFixed(0)}</span>
                  <span className={'pi-pct '+(p.unrealized_pnl_pct>=0?'up':'dn')}>{(p.unrealized_pnl_pct>=0?'+':'')+p.unrealized_pnl_pct.toFixed(1)+'%'}</span>
                </div>
              </div>
            )):<div className="no-pos">No open positions</div>}
          </div>
        </div>

        {/* Quick actions */}
        <div className="side-sec side-quick">
          <div className="sec-h">Quick Actions</div>
          <div className="quick-grid">
            <button className="qk" onClick={()=>sendMessage('close all')}>🔴 Close All</button>
            <button className="qk" onClick={()=>sendMessage('top gainers')}>🔥 Gainers</button>
            <button className="qk" onClick={()=>sendMessage('market regime')}>📊 Market</button>
            <button className="qk" onClick={()=>sendMessage('How did we do today?')}>📋 Recap</button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="main">
        {/* Position detail bar */}
        {selectedPos&&(()=>{var p=positions.find(x=>x.ticker===selectedPos);if(!p)return null;return(
          <div className="pos-bar">
            <div className="pb-left">
              <span className="pb-tk">{p.ticker}</span>
              <span className={'pb-pnl '+(p.unrealized_pnl>=0?'up':'dn')}>{(p.unrealized_pnl>=0?'+':'-')+'$'+Math.abs(p.unrealized_pnl).toFixed(2)+' ('+(p.unrealized_pnl_pct>=0?'+':'')+p.unrealized_pnl_pct.toFixed(2)+'%)'}</span>
              <span className="pb-meta">{Math.abs(p.qty)+' @ $'+(p.avg_entry_price||0).toFixed(2)+' → $'+(p.current_price||0).toFixed(2)+' · '+(p.side==='short'?'SHORT':'LONG')}</span>
            </div>
            <div className="pb-acts">
              <button className="act act-a" onClick={()=>{sendMessage(p.ticker);setSelectedPos(null)}}>Analyze</button>
              <button className="act act-b" onClick={()=>{sendMessage('buy 1 '+p.ticker);setSelectedPos(null)}}>Buy More</button>
              <button className="act act-s" onClick={()=>{sendMessage((p.side==='short'?'cover ':'sell ')+p.ticker);setSelectedPos(null)}}>{p.side==='short'?'Cover':'Sell'}</button>
              <button className="pb-close" onClick={()=>setSelectedPos(null)}>✕</button>
            </div>
          </div>
        )})()}

        {/* Chat */}
        <div className="chat">
          {messages.length===0&&!sending&&(
            <div className="welcome">
              <div className="w-logo">P</div>
              <h2>{getGreeting()}</h2>
              <p className="w-sub">What would you like to know?</p>
              <div className="w-grid">
                {[['📊','Analyze a stock','Signal breakdown','Analyze NVDA'],['🔥','Top gainers','Moving today','top gainers'],['📋','Daily recap','Review trades','How did we do today?'],['🌍','Market health','SPY & VIX','market regime']].map(([icon,title,desc,cmd],i)=>(
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
                <div className="m-ai"><div className="m-av"><div className="av">P</div></div>
                  <div className="m-ai-body">
                    <div className="m-ai-text" dangerouslySetInnerHTML={{__html:fmt(m.content)}}/>
                    {m.ticker&&<div className="m-chart"><Chart ticker={m.ticker} signal={m.signal} height={240}/></div>}
                  </div>
                </div>
              ):(
                <div className="m-user"><div className="m-user-b">{m.content}</div></div>
              )}
            </div>
          ))}
          {sending&&<div className="m"><div className="m-ai"><div className="m-av"><div className="av">P</div></div><div className="m-ai-body"><div className="dots"><span/><span/><span/></div></div></div></div>}
          <div ref={messagesEnd}/>
        </div>
        <div className="inp-area"><div className="inp-box">
          <input ref={inputRef} value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')send()}} placeholder="Message Paula..." disabled={sending}/>
          <button className="inp-send" onClick={send} disabled={sending}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></button>
        </div></div>
      </main>
    </div>
  )
}
function fmt(t){if(!t)return '';return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`(.+?)`/g,'<code>$1</code>').replace(/\n/g,'<br/>')}
export default App
