import { useState, useEffect, useRef, useCallback } from 'react'
import Chart from './Chart'
import { playBuy, playSell, playNotify, playAlert, playProfit, playTick } from './sounds'
import './App.css'

const BACKEND = (import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://127.0.0.1:3141' : 'https://scurrilously-inevasible-kailey.ngrok-free.dev')).replace(/\/+$/, '')
const API = BACKEND
const H = { 'ngrok-skip-browser-warning': '1' }
const f = (url, opts = {}) => fetch(url, { ...opts, headers: { ...H, ...(opts.headers || {}) } })
const WS_URL = `${BACKEND.startsWith('https') ? 'wss:' : 'ws:'}//${new URL(BACKEND).host}/ws`

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [account, setAccount] = useState(null)
  const [positions, setPositions] = useState([])
  const [autopilot, setAutopilot] = useState(false)
  const [connected, setConnected] = useState(false)
  const [spyTrend, setSpyTrend] = useState(null)
  const [selectedPos, setSelectedPos] = useState(null)
  const [toasts, setToasts] = useState([])
  const [view, setView] = useState('chat')
  const [perf, setPerf] = useState(null)
  const [sideOpen, setSideOpen] = useState(window.innerWidth > 768)
  const [settings, setSettings] = useState(() => {
    try { return JSON.parse(localStorage.getItem('paula-settings')) || {} } catch { return {} }
  })
  const settingsRef = useRef(settings)
  useEffect(() => { settingsRef.current = settings }, [settings])
  const updateSetting = (k, v) => { const n = { ...settings, [k]: v }; setSettings(n); localStorage.setItem('paula-settings', JSON.stringify(n)) }
  const snd = (fn) => { if (settingsRef.current.sounds !== false) fn() }

  const messagesEnd = useRef(null)
  const wsRef = useRef(null)
  const inputRef = useRef(null)
  const toastId = useRef(0)

  const addToast = useCallback((msg, type = 'info') => {
    if (settingsRef.current.toasts === false) return
    const id = ++toastId.current
    setToasts(prev => [...prev, { id, msg: msg.replace(/\*\*/g, ''), type }])
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
              if (settingsRef.current.scanSound !== false) playNotify()
              setMessages(prev => [...prev, { role: 'assistant', content: '**Autopilot Scan**\n\n' + data.log.join('\n\n'), type: 'autopilot' }])
            }
          }
          if (event === 'trade') {
            const act = data.action, ticker = data.ticker || data.symbol || ''
            if (act === 'buy') { snd(playBuy); addToast('Bought ' + ticker, 'buy') }
            else if (act === 'sell') { snd(playSell); addToast('Sold ' + ticker, 'sell') }
            else if (act === 'short') { snd(playSell); addToast('Shorted ' + ticker, 'sell') }
            else if (act === 'cover') { snd(playProfit); addToast('Covered ' + ticker, 'buy') }
            else if (act === 'close_all') { snd(playAlert); addToast('All positions closed', 'warn') }
            refreshData()
          }
        } catch {}
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const refreshData = useCallback(async () => {
    try {
      const [a, p, s, h] = await Promise.all([
        f(API+'/api/account').then(r=>r.json()), f(API+'/api/positions').then(r=>r.json()),
        f(API+'/api/spy-trend').then(r=>r.json()), f(API+'/api/health').then(r=>r.json()),
      ])
      if (a.ok) setAccount(a.data); if (p.ok) setPositions(p.data)
      if (s.ok) setSpyTrend(s.data); setAutopilot(h.autopilot)
    } catch {}
  }, [])

  useEffect(() => { f(API+'/api/chat/clear',{method:'POST'}).catch(()=>{}); refreshData(); const i=setInterval(refreshData,5000); return()=>clearInterval(i) }, [refreshData])
  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const sendMessage = async (msg) => {
    if (!msg || sending) return
    setMessages(prev => [...prev, { role: 'user', content: msg }]); setInput(''); setSending(true)
    try {
      const res = await f(API+'/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:msg}) })
      const data = await res.json()
      if (data.ok) {
        setMessages(prev => [...prev, { role:'assistant', content:data.message, type:data.type, ticker:data.ticker||null, signal:data.trade_signal||null }])
        if (data.type==='trade'&&data.message) {
          if(data.message.includes('Bought')){snd(playBuy);addToast(data.message.slice(0,60),'buy')}
          else if(data.message.includes('Sold')||data.message.includes('Shorted')){snd(playSell);addToast(data.message.slice(0,60),'sell')}
          else if(data.message.includes('Covered')){snd(playProfit);addToast(data.message.slice(0,60),'buy')}
          else if(data.message.includes('closed')){addToast(data.message.slice(0,60),'warn')}
        } else snd(playTick)
        if (data.autopilot!==undefined) setAutopilot(data.autopilot)
      } else { snd(playAlert); setMessages(prev=>[...prev,{role:'assistant',content:'Error: '+(data.error||'Unknown')}]) }
      refreshData()
    } catch { setMessages(prev=>[...prev,{role:'assistant',content:'Connection lost.'}]) }
    setSending(false); inputRef.current?.focus()
  }

  const send = () => sendMessage(input.trim())
  const loadDashboard = async () => { try { const r = await f(API+'/api/performance').then(r=>r.json()); if(r.ok)setPerf(r) } catch{} }

  const pnl = account?(account.daily_pnl||0):0, pnlPct = account?(account.daily_pnl_pct||0):0
  const totalUnrealized = positions.reduce((s,p)=>s+(p.unrealized_pnl||0),0)
  const name = settings.userName || 'PJ'

  return (
    <div className="app">
      {/* Toasts */}
      <div className="toasts">{toasts.map(t=>(
        <div key={t.id} className={'toast t-'+t.type}><span className="t-dot"/>{t.msg}
          <button className="t-x" onClick={()=>setToasts(p=>p.filter(x=>x.id!==t.id))}>×</button>
        </div>))}</div>

      {/* Sidebar */}
      <aside className={'sb'+(sideOpen?'':' sb-hide')}>
        <div className="sb-top">
          <div className="sb-logo"><span className="logo-p">P</span>Paula</div>
          <button className="sb-close" onClick={()=>setSideOpen(false)}>×</button>
        </div>
        <nav className="sb-tabs">{['chat','stats','settings'].map(v=>(
          <button key={v} className={'tab'+(view===v?' tab-on':'')} onClick={()=>{setView(v);if(v==='stats')loadDashboard()}}>
            {v==='chat'?'Chat':v==='stats'?'Stats':'Settings'}
          </button>))}</nav>
        {account&&<div className="sb-acct">
          <div className="acct-main">
            <span className="acct-eq">${account.equity.toLocaleString(undefined,{maximumFractionDigits:0})}</span>
            <span className={'acct-chg '+(pnl>=0?'up':'dn')}>{pnl>=0?'+':''}{pnl.toFixed(0)} ({pnlPct>=0?'+':''}{pnlPct.toFixed(2)}%)</span>
          </div>
          {spyTrend&&<span className={'acct-spy '+(spyTrend.change_pct>=0?'up':'dn')}>SPY {spyTrend.change_pct>=0?'+':''}{spyTrend.change_pct}%</span>}
        </div>}
        <button className={'sb-ap'+(autopilot?' ap-go':'')} onClick={()=>sendMessage(autopilot?'stop':'autopilot')}>
          <span className={'ap-dot'+(autopilot?' dot-on':'')}/>{autopilot?'Autopilot On':'Autopilot Off'}
        </button>
        <div className="sb-pos">
          <div className="pos-head">Positions <span className="pos-n">{positions.length}</span>
            {positions.length>0&&<span className={'pos-tot '+(totalUnrealized>=0?'up':'dn')}>{totalUnrealized>=0?'+':''}{totalUnrealized.toFixed(0)}</span>}
          </div>
          <div className="pos-list">{positions.length>0?positions.map((p,i)=>(
            <button key={i} className={'pi'+(selectedPos===p.ticker?' pi-sel':'')+(p.unrealized_pnl>=0?' pi-up':' pi-dn')}
              onClick={()=>setSelectedPos(selectedPos===p.ticker?null:p.ticker)}>
              <div className="pi-l"><span className="pi-sym">{p.ticker}</span><span className="pi-meta">{Math.abs(p.qty)}·{p.side==='short'?'S':'L'}{p.stop_loss?' SL$'+p.stop_loss:''}</span></div>
              <span className="pi-pnl">{p.unrealized_pnl>=0?'+':''}{p.unrealized_pnl.toFixed(0)}</span>
            </button>)):<span className="empty-txt">No positions</span>}</div>
        </div>
        <div className="sb-bottom"><span className={'conn'+(connected?' c-on':'')}>{connected?'● Connected':'○ Offline'}</span></div>
      </aside>

      {/* Main */}
      <main className="main">
        {!sideOpen&&<button className="ham" onClick={()=>setSideOpen(true)}>☰</button>}
        {view==='stats'?<DashView perf={perf}/>
        :view==='settings'?<SetView settings={settings} update={updateSetting}/>
        :(<>
          {selectedPos&&(()=>{const p=positions.find(x=>x.ticker===selectedPos);if(!p)return null;return(
            <div className="detail-bar">
              <div className="db-info">
                <span className="db-sym">{p.ticker}</span>
                <span className={'db-pnl '+(p.unrealized_pnl>=0?'up':'dn')}>{p.unrealized_pnl>=0?'+':'-'}${Math.abs(p.unrealized_pnl).toFixed(2)}</span>
                <span className="db-meta">{Math.abs(p.qty)} @ ${(p.avg_entry||0).toFixed(2)} → ${(p.current_price||0).toFixed(2)}</span>
              </div>
              <div className="db-acts">
                <button className="btn-sm" onClick={()=>{sendMessage(p.ticker);setSelectedPos(null)}}>Analyze</button>
                <button className="btn-sm btn-g" onClick={()=>{sendMessage('buy 1 '+p.ticker);setSelectedPos(null)}}>Buy</button>
                <button className="btn-sm btn-r" onClick={()=>{sendMessage((p.side==='short'?'cover ':'sell ')+p.ticker);setSelectedPos(null)}}>{p.side==='short'?'Cover':'Sell'}</button>
                <button className="btn-x" onClick={()=>setSelectedPos(null)}>×</button>
              </div>
              <div className="db-chart"><Chart ticker={p.ticker} signal={null} height={200}/></div>
            </div>)})()}
          <div className="chat">
            {messages.length===0&&!sending&&(
              <div className="welcome">
                <h1><span className="w-hi">Hey {name},</span> {(() => {
                  const lines = ["what's the play today?", "ready to trade?", "let's find some setups.", "what are we watching?", "let's get to work.", "what's on your radar?", "let's make some moves."]
                  return lines[Math.floor(Math.random() * lines.length)]
                })()}</h1>
                <div className="w-pills">
                  {[['Market overview','market regime'],['Top movers','top gainers'],['Today\'s recap','How did we do today?'],['Find trades','What should I buy?'],['Analyze a stock','Analyze ']].map(([l,c],i)=>(
                    <button key={i} className="pill" onClick={()=>{if(c==='Analyze '){setInput(c);inputRef.current?.focus()}else sendMessage(c)}}>{l}</button>))}</div>
              </div>)}
            {messages.map((m,i)=>(
              <div key={i} className={'msg msg-'+m.role}>
                {m.role==='assistant'?(<div className="ai"><div className="ai-av">P</div><div className="ai-body">
                  <div className="ai-txt" dangerouslySetInnerHTML={{__html:fmt(m.content)}}/>
                  {m.ticker&&<div className="ai-chart"><Chart ticker={m.ticker} signal={m.signal} height={260}/></div>}
                </div></div>):(<div className="user-bubble">{m.content}</div>)}
              </div>))}
            {sending&&<div className="msg"><div className="ai"><div className="ai-av">P</div><div className="ai-body"><div className="dots"><span/><span/><span/></div></div></div></div>}
            <div ref={messagesEnd}/>
          </div>
          <div className="input-area"><div className="input-box">
            <input ref={inputRef} value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')send()}} placeholder="Message Paula..." disabled={sending}/>
            <button className="send" onClick={send} disabled={sending}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9Z"/></svg></button>
          </div></div>
        </>)}
      </main>
    </div>)
}

function DashView({perf}){
  if(!perf)return <div className="view-msg">Loading...</div>
  return(<div className="view-scroll"><h2 className="view-h">Performance</h2>
    {perf.pnl_history?.length>1&&<div className="card wide"><label>Equity</label><EqChart data={perf.pnl_history}/></div>}
    <div className="card-row">
      <div className="card"><label>Trades</label><span className="big">{perf.total_trades}</span></div>
      <div className="card"><label>Config</label><div className="params">{perf.current_params&&Object.entries(perf.current_params).map(([k,v])=>(
        <div key={k} className="pr"><span>{k}</span><span>{typeof v==='number'?(v<1&&v>0?(v*100).toFixed(1)+'%':v):String(v)}</span></div>))}</div></div>
    </div>
    {perf.tune_history?.length>0&&<div className="card wide"><label>Auto-Tune</label>{perf.tune_history.slice().reverse().map((h,i)=>(
      <div key={i} className="tune"><span className="t-date">{h.date}</span><span className={'t-pnl '+(((h.stats?.pnl)||0)>=0?'up':'dn')}>{(h.stats?.pnl>=0?'+':'')+'$'+Math.abs(h.stats?.pnl||0).toFixed(0)}</span><span className="t-wr">{h.stats?.wins}W {h.stats?.losses}L</span><div className="t-ch">{h.changes?.map((c,j)=><div key={j}>{c}</div>)}</div></div>))}</div>}
    {perf.recent_trades?.length>0&&<div className="card wide"><label>Recent</label>{perf.recent_trades.slice().reverse().slice(0,12).map((t,i)=>(
      <div key={i} className="tr-row"><span className={'tr-act '+(t.action==='buy'?'up':'dn')}>{t.action?.toUpperCase()}</span><span className="tr-sym">{t.ticker}</span><span className="tr-time">{t.time?.slice(11,16)}</span></div>))}</div>}
  </div>)
}

function SetView({settings,update}){
  return(<div className="view-scroll"><h2 className="view-h">Settings</h2>
    <div className="card wide"><label>Sounds</label>
      <Tog l="Trade sounds" on={settings.sounds!==false} fn={()=>update('sounds',!(settings.sounds!==false))}/>
      <Tog l="Scan notification" on={settings.scanSound!==false} fn={()=>update('scanSound',!(settings.scanSound!==false))}/>
    </div>
    <div className="card wide"><label>Notifications</label>
      <Tog l="Toast popups" on={settings.toasts!==false} fn={()=>update('toasts',!(settings.toasts!==false))}/>
      <Tog l="Phone push" on={settings.pushNotif!==false} fn={()=>update('pushNotif',!(settings.pushNotif!==false))}/>
    </div>
    <div className="card wide"><label>Display</label>
      <div className="s-row"><span>Name</span><input className="s-inp" value={settings.userName||'PJ'} onChange={e=>update('userName',e.target.value)}/></div>
    </div>
  </div>)
}

function Tog({l,on,fn}){return <div className="s-row"><span>{l}</span><button className={'tog'+(on?' tog-on':'')} onClick={fn}>{on?'ON':'OFF'}</button></div>}

function EqChart({data}){
  if(!data||data.length<2)return null
  const v=data.map(d=>d.equity||d.value||0).filter(x=>x>0);if(v.length<2)return null
  const mn=Math.min(...v),mx=Math.max(...v),rng=mx-mn||1,W=600,H=130,P=20
  const pts=v.map((y,i)=>`${P+(i/(v.length-1))*(W-P*2)},${P+(1-(y-mn)/rng)*(H-P*2)}`).join(' ')
  const up=v[v.length-1]>=v[0]
  return(<svg viewBox={`0 0 ${W} ${H}`} className="eq-svg">
    <defs><linearGradient id="eg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={up?'#00dda0':'#f04060'} stopOpacity=".12"/><stop offset="100%" stopColor={up?'#00dda0':'#f04060'} stopOpacity="0"/></linearGradient></defs>
    <polygon points={`${P},${H-P} ${pts} ${W-P},${H-P}`} fill="url(#eg)"/>
    <polyline points={pts} fill="none" stroke={up?'#00dda0':'#f04060'} strokeWidth="1.5"/>
  </svg>)
}

function fmt(t){if(!t)return '';return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`(.+?)`/g,'<code>$1</code>').replace(/\n/g,'<br/>')}
export default App
