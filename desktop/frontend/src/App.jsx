import { useState, useEffect, useRef, useCallback } from 'react'
import Chart from './Chart'
import { playBuy, playSell, playNotify, playAlert, playProfit, playTick } from './sounds'
import './App.css'

const BACKEND = (import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://127.0.0.1:3141' : 'https://scurrilously-inevasible-kailey.ngrok-free.dev')).replace(/\/+$/, '')
const API = BACKEND
const H = { 'ngrok-skip-browser-warning': '1' }
const f = (url, opts = {}) => {
  const headers = { ...H, ...(opts.headers || {}) }
  const tk = localStorage.getItem('paula-token')
  if (tk) headers['Authorization'] = 'Bearer ' + tk
  return fetch(url, { ...opts, headers })
}
const WS_URL = `${BACKEND.startsWith('https') ? 'wss:' : 'ws:'}//${new URL(BACKEND).host}/ws`

function App() {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('paula-token'))
  const [authLoading, setAuthLoading] = useState(true)

  // Check auth on mount
  useEffect(() => {
    if (token) {
      f(API + '/api/auth/me', { headers: { 'Authorization': 'Bearer ' + token } })
        .then(r => r.json())
        .then(data => { if (data.ok) setUser(data.user); else { setToken(null); localStorage.removeItem('paula-token') } })
        .catch(() => {})
        .finally(() => setAuthLoading(false))
    } else { setAuthLoading(false) }
  }, [token])

  const doAuth = async (username, password, isSignup) => {
    const res = await f(API + '/api/auth/' + (isSignup ? 'signup' : 'login'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    }).then(r => r.json())
    if (res.ok) {
      setToken(res.token); setUser(res.user); localStorage.setItem('paula-token', res.token)
      // Auto-set display name from username
      const s = JSON.parse(localStorage.getItem('paula-settings') || '{}')
      if (!s.userName) { s.userName = res.user.username; localStorage.setItem('paula-settings', JSON.stringify(s)) }
    }
    return res
  }

  const logout = () => { setUser(null); setToken(null); localStorage.removeItem('paula-token') }

  if (authLoading) return <div className="auth-loading"><div className="logo-p">P</div></div>
  if (!user) return <LoginPage onAuth={doAuth} />

  return <MainApp user={user} token={token} logout={logout} />
}

function LoginPage({ onAuth }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [isSignup, setIsSignup] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e?.preventDefault()
    if (!username || !password) return
    setLoading(true); setError('')
    const res = await onAuth(username, password, isSignup)
    if (!res.ok) setError(res.error)
    setLoading(false)
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="logo-p">P</div>
          <h1>Paula</h1>
          <p>{isSignup ? 'Create your account' : 'Welcome back'}</p>
        </div>
        <div className="login-form">
          <input className="login-input" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') submit() }} autoFocus autoComplete="username" />
          <div className="pw-wrap">
            <input className="login-input pw-input" type={showPw ? 'text' : 'password'} placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') submit() }} autoComplete={isSignup ? 'new-password' : 'current-password'} />
            <button type="button" className="pw-eye" onClick={() => setShowPw(!showPw)}>
              {showPw ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                     : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>}
            </button>
          </div>
          {error && <div className="login-error">{error}</div>}
          <button className="login-btn" onClick={submit} disabled={loading}>
            {loading ? '...' : isSignup ? 'Create Account' : 'Sign In'}
          </button>
          <button className="login-toggle" onClick={() => { setIsSignup(!isSignup); setError('') }}>
            {isSignup ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
          </button>
          <a href="/commercial.html" target="_blank" className="login-trailer">▶ Watch Trailer</a>
        </div>
      </div>
    </div>
  )
}

function MainApp({ user, token, logout }) {
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

  // ── Chat system (localStorage-backed) ──
  const chatsRef = useRef(JSON.parse(localStorage.getItem('paula-chats') || '[]'))
  const [chats, _setChats] = useState(chatsRef.current)
  const [chatId, setChatId] = useState(localStorage.getItem('paula-current-chat') || null)

  const persistChats = (updated) => {
    chatsRef.current = updated
    _setChats(updated)
    localStorage.setItem('paula-chats', JSON.stringify(updated))
  }

  const newChat = () => {
    // Save current messages first
    if (chatId && messages.length > 0) {
      const updated = chatsRef.current.map(c => c.id === chatId ? { ...c, messages } : c)
      persistChats(updated)
    }
    const id = Date.now().toString()
    persistChats([{ id, title: 'New chat', messages: [], created: new Date().toISOString() }, ...chatsRef.current])
    setChatId(id)
    setMessages([])
    localStorage.setItem('paula-current-chat', id)
    // Clear backend chat context
    f(API + '/api/chat/clear', { method: 'POST' }).catch(() => {})
  }

  const switchChat = (id) => {
    if (id === chatId) return
    // Save current
    if (chatId && messages.length > 0) {
      const updated = chatsRef.current.map(c => c.id === chatId ? { ...c, messages } : c)
      persistChats(updated)
    }
    setChatId(id)
    localStorage.setItem('paula-current-chat', id)
    const chat = chatsRef.current.find(c => c.id === id)
    setMessages(chat?.messages || [])
    // Clear backend chat context so AI doesn't reference old chat
    f(API + '/api/chat/clear', { method: 'POST' }).catch(() => {})
  }

  const deleteChat = (id) => {
    const updated = chatsRef.current.filter(c => c.id !== id)
    persistChats(updated)
    if (chatId === id) {
      if (updated.length > 0) { setChatId(updated[0].id); setMessages(updated[0].messages || []) }
      else { setChatId(null); setMessages([]) }
    }
  }

  // Save messages to current chat (debounced, no circular deps)
  const saveTimer = useRef(null)
  useEffect(() => {
    if (!chatId || messages.length === 0) return
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      const updated = chatsRef.current.map(c => c.id === chatId ? { ...c, messages } : c)
      chatsRef.current = updated
      _setChats(updated)
      localStorage.setItem('paula-chats', JSON.stringify(updated))
    }, 500)
  }, [messages, chatId])
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
            if (data.status === 'started') { setAutopilot(true) }
            if (data.status === 'stopped') { setAutopilot(false) }
            if (data.log) {
              if (settingsRef.current.scanSound !== false) playNotify()
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

  useEffect(() => {
    // Load current chat messages on mount
    if (chatId) {
      const chat = chatsRef.current.find(c => c.id === chatId)
      if (chat?.messages) setMessages(chat.messages)
    }
    refreshData()
    const i = setInterval(refreshData, 5000)
    return () => clearInterval(i)
  }, [refreshData])
  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const sendMessage = async (msg) => {
    if (!msg || sending) return
    let targetChatId = chatId
    const isFirstMessage = !messages.length
    if (!chatId) {
      targetChatId = Date.now().toString()
      persistChats([{ id: targetChatId, title: 'New chat', messages: [], created: new Date().toISOString() }, ...chatsRef.current])
      setChatId(targetChatId)
      setView('chat')
      localStorage.setItem('paula-current-chat', targetChatId)
    }
    setMessages(prev => [...prev, { role: 'user', content: msg }]); setInput(''); setSending(true)
    try {
      let res
      try {
        res = await f(API+'/api/chat/stream', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:msg}) })
      } catch {
        // Stream endpoint failed — fall back to regular chat
        res = await f(API+'/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:msg}) })
      }

      // If stream returned error, fall back
      if (!res.ok) {
        try {
          const fallback = await f(API+'/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:msg}) })
          const data = await fallback.json()
          if (data.ok) {
            setMessages(prev => [...prev, { role:'assistant', content:data.message, type:data.type, ticker:data.ticker||null, signal:data.trade_signal||null }])
            snd(playTick)
          }
          if (isFirstMessage && targetChatId) {
            f(API+'/api/chat/title', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:msg}) })
              .then(r=>r.json()).then(t=>{ if (t.ok && t.title) { persistChats(chatsRef.current.map(c => c.id === targetChatId ? { ...c, title: t.title } : c)) } }).catch(()=>{})
          }
          refreshData()
          setSending(false); inputRef.current?.focus()
          return
        } catch {}
      }

      const contentType = res.headers.get('content-type') || ''

      if (contentType.includes('text/event-stream')) {
        // Streaming response — show text as it comes
        setMessages(prev => [...prev, { role:'assistant', content:'', type:'chat', streaming:true }])
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let fullText = ''
        let meta = {}

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const text = decoder.decode(value, { stream: true })
          const lines = text.split('\n').filter(l => l.startsWith('data: '))
          for (const line of lines) {
            try {
              const d = JSON.parse(line.slice(6))
              if (d.chunk) {
                fullText += d.chunk
                setMessages(prev => {
                  const msgs = [...prev]
                  const last = msgs[msgs.length - 1]
                  if (last && last.streaming) msgs[msgs.length - 1] = { ...last, content: fullText }
                  return msgs
                })
              }
              if (d.done) meta = d
            } catch {}
          }
        }

        // Finalize — remove streaming flag, add metadata
        setMessages(prev => {
          const msgs = [...prev]
          const last = msgs[msgs.length - 1]
          if (last) msgs[msgs.length - 1] = { ...last, streaming: false, type: meta.type||'chat', ticker: meta.ticker||null, signal: meta.trade_signal||null }
          return msgs
        })
        snd(playTick)
      } else {
        // Non-streaming JSON response (trades, instant replies)
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
      }

      // Generate title for new chats
      if (isFirstMessage && targetChatId) {
        f(API+'/api/chat/title', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:msg}) })
          .then(r=>r.json()).then(t=>{
            if (t.ok && t.title) { persistChats(chatsRef.current.map(c => c.id === targetChatId ? { ...c, title: t.title } : c)) }
          }).catch(()=>{ persistChats(chatsRef.current.map(c => c.id === targetChatId && c.title === 'New chat' ? { ...c, title: msg.slice(0, 35) } : c)) })
      }
      refreshData()
    } catch { setMessages(prev=>[...prev,{role:'assistant',content:'Connection lost.'}]) }
    setSending(false); inputRef.current?.focus()
  }

  const send = () => sendMessage(input.trim())
  const loadDashboard = async () => { try { const r = await f(API+'/api/performance').then(r=>r.json()); if(r.ok)setPerf(r) } catch{} }

  const pnl = account?(account.daily_pnl||0):0, pnlPct = account?(account.daily_pnl_pct||0):0
  const totalUnrealized = positions.reduce((s,p)=>s+(p.unrealized_pnl||0),0)
  const name = settings.userName || user?.username || 'PJ'

  return (
    <div className="app">
      {/* Toasts */}
      <div className="toasts">{toasts.map(t=>(
        <div key={t.id} className={'toast t-'+t.type}><span className="t-dot"/>{t.msg}
          <button className="t-x" onClick={()=>setToasts(p=>p.filter(x=>x.id!==t.id))}>×</button>
        </div>))}</div>
      {/* Sidebar — chats + positions only */}
      <aside className={'sb'+(sideOpen?'':' sb-hide')}>
        <div className="sb-top">
          <div className="sb-logo"><span className="logo-p">P</span>Paula</div>
          <button className="sb-close" onClick={()=>setSideOpen(false)}>×</button>
        </div>
        <button className="new-chat" onClick={newChat}>+ New Chat</button>
        <div className="chat-list">
          {chats.slice(0, 20).map(c => (
            <div key={c.id} className={'chat-item' + (chatId === c.id ? ' ci-active' : '')} onClick={() => {switchChat(c.id);setView('chat')}}>
              <span className="ci-icon">{chatEmoji(c.title)}</span>
              <span className="ci-title">{c.title}</span>
              <button className="ci-del" onClick={(e) => { e.stopPropagation(); deleteChat(c.id) }}>×</button>
            </div>
          ))}
        </div>
        <div className="sb-pos">
          <div className="pos-head">Positions <span className="pos-n">{positions.length}</span>
            {positions.length>0&&<span className={'pos-tot '+(totalUnrealized>=0?'up':'dn')}>{totalUnrealized>=0?'+':''}{totalUnrealized.toFixed(0)}</span>}
          </div>
          <div className="pos-list">{positions.length>0?positions.map((p,i)=>(
            <button key={i} className={'pi'+(selectedPos===p.ticker?' pi-sel':'')+(p.unrealized_pnl>=0?' pi-up':' pi-dn')}
              onClick={()=>setSelectedPos(selectedPos===p.ticker?null:p.ticker)}>
              <div className="pi-l"><span className="pi-sym">{p.ticker}</span><span className="pi-meta">{Math.abs(p.qty)}·{p.side==='short'?'S':'L'}{p.stop_loss?' SL$'+p.stop_loss:''}</span></div>
              <span className="pi-pnl">{p.unrealized_pnl>=0?'+':''}{p.unrealized_pnl.toFixed(0)}</span>
            </button>)):<span className="empty-txt">Flat</span>}</div>
        </div>
        <div className="sb-bottom">
          <span className={'conn'+(connected?' c-on':'')}>{connected?'● Connected':'○ Offline'}</span>
        </div>
      </aside>

      {/* Main */}
      <main className="main">
        {!sideOpen&&<button className="ham" onClick={()=>setSideOpen(true)}>☰</button>}

        {/* Header bar — account, nav, autopilot */}
        <div className="hdr">
          <div className="hdr-left">
            {account&&<>
              <span className="hdr-eq">${account.equity.toLocaleString(undefined,{maximumFractionDigits:0})}</span>
              <span className={'hdr-pnl '+(pnl>=0?'up':'dn')}>{pnl>=0?'+':''}{pnl.toFixed(0)}</span>
              {spyTrend&&<span className={'hdr-spy '+(spyTrend.change_pct>=0?'up':'dn')}>SPY {spyTrend.change_pct>=0?'+':''}{spyTrend.change_pct}%</span>}
            </>}
          </div>
          <nav className="hdr-nav">
            {[['chat','Chat'],['stats','Stats'],['settings','Settings']].map(([v,label])=>(
              <button key={v} className={'hdr-tab'+(view===v?' ht-on':'')} onClick={()=>{setView(v);if(v==='stats')loadDashboard()}}>{label}</button>
            ))}
          </nav>
          <div className="hdr-right">
            <button className={'hdr-ap'+(autopilot?' hap-on':'')} onClick={async ()=>{
              try { await f(API+'/api/autopilot/'+(autopilot?'stop':'start'),{method:'POST'}); refreshData() } catch{}
            }}>
              <span className={'ap-dot'+(autopilot?' dot-on':'')}/>{autopilot?'On':'Off'}
            </button>
            <button className="hdr-logout" onClick={logout}>Sign out</button>
          </div>
        </div>

        {view==='stats'?<DashView perf={perf}/>
        
        :view==='settings'?<SetView settings={settings} update={updateSetting} user={user} token={token} logout={logout}/>
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
            <div className="chat-inner">
            {messages.length===0&&!sending&&(
              <div className="welcome">
                <h1><span className="w-hi">Hey {name},</span> <Typewriter/></h1>
                <div className="w-pills">
                  {[['Market overview','market regime'],['Top movers','top gainers'],["Today's recap",'How did we do today?'],['Find trades','What should I buy?'],['Analyze a stock','Analyze ']].map(([l,c],i)=>(
                    <button key={i} className="pill" disabled={sending} onClick={()=>{if(c==='Analyze '){setInput(c);inputRef.current?.focus()}else sendMessage(c)}}>{l}</button>))}</div>
              </div>)}
            {messages.map((m,i)=>(
              <div key={i} className={'msg msg-'+m.role}>
                {m.role==='assistant'?(
                  <div className="ai">
                    <div className="ai-av">P</div>
                    <div className="ai-body">
                      <div className="ai-name">Paula</div>
                      <div className="ai-txt"><span dangerouslySetInnerHTML={{__html:fmt(m.content)}}/>{m.streaming&&<span className="stream-cursor">▌</span>}</div>
                      {m.ticker&&<div className="ai-chart"><Chart ticker={m.ticker} signal={m.signal} height={260}/></div>}
                    </div>
                  </div>
                ):(<div className="user-bubble">{m.content}</div>)}
              </div>))}
            {sending&&!messages.some(m=>m.streaming)&&<div className="msg msg-assistant"><div className="ai"><div className="ai-av">P</div><div className="ai-body"><div className="ai-name">Paula</div><div className="dots"><span/><span/><span/></div></div></div></div>}
            <div ref={messagesEnd}/>
            </div>
          </div>
          <div className={'input-area'+(messages.length?' ia-active':'')}><div className="input-wrap"><div className="input-box">
            <input ref={inputRef} value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')send()}} placeholder="Message Paula..." disabled={sending}/>
            <button className="send" onClick={send} disabled={sending}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9Z"/></svg></button>
          </div></div></div>
        </>)}
      </main>
    </div>)
}

const PHRASES = ["what's the play today?","ready to trade?","let's find some setups.","what are we watching?","let's get to work.","what's on your radar?","let's make some moves."]
function Typewriter() {
  const [display, setDisplay] = useState('')
  const state = useRef({ idx: 0, charIdx: 0, deleting: false, paused: false })
  useEffect(() => {
    const tick = () => {
      const s = state.current
      const phrase = PHRASES[s.idx % PHRASES.length]
      if (s.paused) return
      if (!s.deleting) {
        s.charIdx++
        setDisplay(phrase.slice(0, s.charIdx))
        if (s.charIdx >= phrase.length) {
          s.paused = true
          setTimeout(() => { s.paused = false; s.deleting = true }, 8000)
        }
      } else {
        s.charIdx--
        setDisplay(phrase.slice(0, s.charIdx))
        if (s.charIdx <= 0) {
          s.deleting = false
          s.idx++
        }
      }
    }
    const id = setInterval(tick, state.current.deleting ? 30 : 60)
    return () => clearInterval(id)
  }, [])
  return <span className="tw">{display}<span className="cursor">|</span></span>
}

function DashView({perf}){
  const [period, setPeriod] = useState('1M')
  const [data, setData] = useState(perf)
  const loadPeriod = async (p) => {
    setPeriod(p)
    try { const r = await f(API+'/api/performance?period='+p).then(r=>r.json()); if(r.ok)setData(r) } catch{}
  }
  useEffect(()=>{if(perf)setData(perf)},[perf])
  const d = data || perf
  if(!d)return <div className="view-msg">Loading...</div>

  const startEq = d.pnl_history?.[0]?.equity || 0
  const endEq = d.pnl_history?.[d.pnl_history.length-1]?.equity || 0
  const totalChg = endEq - startEq
  const totalPct = startEq > 0 ? ((endEq/startEq - 1)*100) : 0

  return(<div className="view-scroll"><h2 className="view-h">Performance</h2>
    {/* Period selector */}
    <div className="period-bar">
      {[['1D','Day'],['1W','Week'],['1M','Month'],['3M','3M'],['6M','6M'],['1A','YTD'],['all','All']].map(([k,label])=>(
        <button key={k} className={'per-btn'+(period===k?' per-on':'')} onClick={()=>loadPeriod(k)}>{label}</button>
      ))}
    </div>

    {/* Equity chart card */}
    <div className="eq-card">
      <div className="eq-header">
        <div>
          <span className="eq-title">Portfolio Value</span>
          <span className="eq-value">${(d.equity||endEq||0).toLocaleString(undefined,{maximumFractionDigits:0})}</span>
        </div>
        <div className="eq-change">
          <span className={(totalChg>=0?'up':'dn')+' eq-chg'}>{totalChg>=0?'+':''}{totalChg.toFixed(0)}</span>
          <span className={(totalPct>=0?'up':'dn')+' eq-pct'}>{totalPct>=0?'+':''}{totalPct.toFixed(2)}%</span>
        </div>
      </div>
      {d.pnl_history?.length>1 ? <EqChart data={d.pnl_history}/> : <div className="eq-empty">No data for this period</div>}
    </div>

    {/* Stats row */}
    <div className="stat-row">
      <div className="stat-card"><span className="stat-n">{d.total_trades}</span><span className="stat-l">Trades</span></div>
      <div className="stat-card"><span className={'stat-n '+(d.daily_pnl>=0?'up':'dn')}>{d.daily_pnl>=0?'+':''}{(d.daily_pnl||0).toFixed(0)}</span><span className="stat-l">Today</span></div>
      <div className="stat-card"><span className={'stat-n '+(totalChg>=0?'up':'dn')}>{totalChg>=0?'+':''}{totalChg.toFixed(0)}</span><span className="stat-l">{period} P&L</span></div>
    </div>

    {/* Recaps */}
    {d.recaps?.length>0&&<div className="card wide"><label>{{daily:'Daily Recap',weekly:'Weekly Recap',monthly:'Monthly Recap'}[d.recap_type||'daily']}</label>
      {d.recaps.map((r,i)=>{
        const type = d.recap_type||'daily'
        const dateLabel = type==='monthly'
          ? new Date(r.date+'T12:00:00').toLocaleDateString('en-US',{month:'long',year:'numeric'})
          : type==='weekly'
          ? new Date(r.date+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})+' — '+(r.end_date?new Date(r.end_date+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'}):'')
          : new Date(r.date+'T12:00:00').toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'})
        return(
        <div key={i} className="recap-day">
          <div className="recap-head">
            <span className="recap-date">{dateLabel}</span>
            <span className={'recap-pnl '+((r.pnl||0)>=0?'up':'dn')}>{(r.pnl||0)>=0?'+':''}{(r.pnl||0).toFixed(0)}</span>
            <span className="recap-count">{r.trades} trades{r.days>1?' · '+r.days+' days':''}</span>
          </div>
          <div className="recap-detail">
            <span className="recap-bs">{r.buys}B / {r.sells}S</span>
            <span className="recap-tickers">{r.tickers?.join(', ')}</span>
          </div>
        </div>)})}
    </div>}

    {/* Config */}
    {d.current_params&&<div className="card wide"><label>Auto-Tuner Config</label>
      <div className="params">{Object.entries(d.current_params).map(([k,v])=>(
        <div key={k} className="pr"><span>{k}</span><span>{typeof v==='number'?(v<1&&v>0?(v*100).toFixed(1)+'%':v):String(v)}</span></div>))}</div>
    </div>}

    {/* Tune history */}
    {d.tune_history?.length>0&&<div className="card wide"><label>Auto-Tune Log</label>{d.tune_history.slice().reverse().map((h,i)=>(
      <div key={i} className="tune"><span className="t-date">{h.date}</span><span className={'t-pnl '+((h.stats?.pnl||0)>=0?'up':'dn')}>{h.stats?.pnl>=0?'+':''}${Math.abs(h.stats?.pnl||0).toFixed(0)}</span><span className="t-wr">{h.stats?.wins}W {h.stats?.losses}L</span><div className="t-ch">{h.changes?.map((c,j)=><div key={j}>{c}</div>)}</div></div>))}</div>}
    {/* Recent trades */}
    {d.recent_trades?.length>0&&<div className="card wide"><label>Recent Trades</label>{d.recent_trades.slice().reverse().slice(0,12).map((t,i)=>(
      <div key={i} className="tr-row"><span className={'tr-act '+(t.action==='buy'?'up':'dn')}>{t.action?.toUpperCase()}</span><span className="tr-sym">{t.ticker}</span><span className="tr-time">{t.time?.slice(11,16)}</span></div>))}</div>}
  </div>)
}

function SetView({settings,update,user,token,logout}){
  const [keys, setKeys] = useState({alpaca_key:'',alpaca_secret:'',groq_key:'',polygon_key:''})
  const [keySaved, setKeySaved] = useState(false)
  const [keyLoaded, setKeyLoaded] = useState(false)

  // Load saved keys on mount
  useEffect(()=>{
    if(token&&!keyLoaded){
      f(API+'/api/auth/me').then(r=>r.json()).then(d=>{
        if(d.ok&&d.settings){
          setKeys({
            alpaca_key:d.settings.alpaca_key||'',
            alpaca_secret:d.settings.alpaca_secret||'',
            groq_key:d.settings.groq_key||'',
            polygon_key:d.settings.polygon_key||'',
          })
        }
        setKeyLoaded(true)
      }).catch(()=>setKeyLoaded(true))
    }
  },[token])

  const saveKeys = async ()=>{
    const res = await f(API+'/api/auth/settings',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...keys,display_name:settings.userName||user?.username||''})
    }).then(r=>r.json())
    if(res.ok){setKeySaved(true);setTimeout(()=>setKeySaved(false),2000)}
  }

  return(<div className="view-scroll"><h2 className="view-h">Settings</h2>
    {/* Account */}
    {user&&<div className="card wide"><label>Account</label>
      <div className="s-row"><span>Logged in as</span><span className="s-user">{user.username}</span></div>
      <div className="s-row"><span>Sign out</span><button className="tog" onClick={logout}>Logout</button></div>
    </div>}

    {/* API Keys */}
    {user&&<div className="card wide"><label>Alpaca</label>
      <div className="s-row"><span>Alpaca Key</span><input className="s-inp s-wide" type="password" autoComplete="off" value={keys.alpaca_key} onChange={e=>setKeys({...keys,alpaca_key:e.target.value})} placeholder="••••••••"/></div>
      <div className="s-row"><span>Alpaca Secret</span><input className="s-inp s-wide" type="password" autoComplete="off" value={keys.alpaca_secret} onChange={e=>setKeys({...keys,alpaca_secret:e.target.value})} placeholder="••••••••"/></div>
      <button className={'login-btn s-save'+(keySaved?' s-saved':'')} onClick={saveKeys}>{keySaved?'✓ Saved':'Save Keys'}</button>
    </div>}

    <div className="card wide"><label>Sounds</label>
      <Tog l="Trade sounds" on={settings.sounds!==false} fn={()=>update('sounds',!(settings.sounds!==false))}/>
      <Tog l="Scan notification" on={settings.scanSound!==false} fn={()=>update('scanSound',!(settings.scanSound!==false))}/>
    </div>
    <div className="card wide"><label>Notifications</label>
      <Tog l="Toast popups" on={settings.toasts!==false} fn={()=>update('toasts',!(settings.toasts!==false))}/>
      <Tog l="Phone push" on={settings.pushNotif!==false} fn={()=>update('pushNotif',!(settings.pushNotif!==false))}/>
    </div>
    <div className="card wide"><label>Display</label>
      <div className="s-row"><span>Name</span><input className="s-inp" value={settings.userName||user?.username||''} onChange={e=>update('userName',e.target.value)} placeholder="Your name"/></div>
    </div>
  </div>)
}

function Tog({l,on,fn}){return <div className="s-row"><span>{l}</span><button className={'tog'+(on?' tog-on':'')} onClick={fn}>{on?'ON':'OFF'}</button></div>}

function EqChart({data}){
  const [hover, setHover] = useState(null)
  if(!data||data.length<2)return null
  const v=data.map(d=>d.equity||0).filter(x=>x>0);if(v.length<2)return null
  const pnls=data.map(d=>d.pnl||0)
  const mn=Math.min(...v),mx=Math.max(...v),rng=mx-mn||1,W=700,H=180,P=30
  const pts=v.map((y,i)=>[P+(i/(v.length-1))*(W-P*2), P+(1-(y-mn)/rng)*(H-P*2)])
  const line=pts.map(p=>p.join(",")).join(" ")
  const up=v[v.length-1]>=v[0]
  const col=up?"#00dda0":"#f04060"
  const gridY=[0,.25,.5,.75,1].map(f=>P+(1-f)*(H-P*2))
  const gridLabels=[mn,mn+rng*.25,mn+rng*.5,mn+rng*.75,mx]
  const onMove=(e)=>{const svg=e.currentTarget,rect=svg.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*W;let cl=0,md=Infinity;for(let i=0;i<pts.length;i++){const d=Math.abs(pts[i][0]-x);if(d<md){md=d;cl=i}};setHover(cl)}
  const hi=hover,hPt=hi!==null?pts[hi]:null,hVal=hi!==null?v[hi]:null,hPnl=hi!==null?pnls[hi]:null
  const hDate=hi!==null&&data[hi]&&data[hi].ts?new Date(data[hi].ts*1000).toLocaleDateString("en-US",{month:"short",day:"numeric"}):""
  return(<svg viewBox={"0 0 "+W+" "+H} className="eq-svg" onMouseMove={onMove} onMouseLeave={()=>setHover(null)} style={{cursor:"crosshair"}}>
    <defs><linearGradient id="eqfill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={col} stopOpacity=".18"/><stop offset="100%" stopColor={col} stopOpacity="0"/></linearGradient></defs>
    {gridY.map((y,i)=><line key={i} x1={P} y1={y} x2={W-P} y2={y} stroke="#1a1c26" strokeWidth="1"/>)}
    {gridLabels.map((val,i)=><text key={i} x={P-4} y={gridY[i]+3} fill="#3a3c50" fontSize="8" fontFamily="Geist Mono" textAnchor="end">{"$"+(val/1000).toFixed(1)+"k"}</text>)}
    <polygon points={P+","+(H-P)+" "+line+" "+(W-P)+","+(H-P)} fill="url(#eqfill)"/>
    <polyline points={line} fill="none" stroke={col} strokeWidth="2" strokeLinejoin="round"/>
    <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="3" fill={col}/>
    <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="6" fill={col} opacity=".2"/>
    {hPt&&<>
      <line x1={hPt[0]} y1={P} x2={hPt[0]} y2={H-P} stroke={col} strokeWidth="1" opacity=".4" strokeDasharray="3,3"/>
      <circle cx={hPt[0]} cy={hPt[1]} r="4" fill={col} stroke="#09090b" strokeWidth="2"/>
      <rect x={hPt[0]-52} y={hPt[1]-38} width="104" height="30" rx="6" fill="#14161e" stroke="#1e1e26" strokeWidth="1"/>
      <text x={hPt[0]} y={hPt[1]-23} fill={col} fontSize="10" fontFamily="Geist Mono" fontWeight="600" textAnchor="middle">{"$"+(hVal||0).toLocaleString(undefined,{maximumFractionDigits:0})}</text>
      <text x={hPt[0]} y={hPt[1]-13} fill="#8e90a6" fontSize="7" fontFamily="Geist Mono" textAnchor="middle">{hDate+(hPnl?" · "+(hPnl>=0?"+":"")+hPnl.toFixed(0):"")}</text>
    </>}
  </svg>)
}
function chatEmoji(title) {
  if (!title) return '💬'
  const t = title.toLowerCase()
  if (/market.*regime|regime|bull|bear|spy/i.test(t)) return '🌍'
  if (/gain|mover|top|trending|hot/i.test(t)) return '🔥'
  if (/recap|review|today|performance|how did/i.test(t)) return '📊'
  if (/buy|bought|long|order/i.test(t)) return '📈'
  if (/sell|sold|short|cover/i.test(t)) return '📉'
  if (/trade.*idea|find|setup|scan|pick/i.test(t)) return '🎯'
  if (/autopilot|auto|bot|run/i.test(t)) return '🤖'
  if (/risk|stop|loss|drawdown/i.test(t)) return '🛡️'
  if (/news|earnings|report/i.test(t)) return '📰'
  if (/sector|rotation|etf/i.test(t)) return '🏭'
  if (/portfolio|equity|account|balance/i.test(t)) return '💰'
  if (/chart|technical|rsi|macd|vwap/i.test(t)) return '📉'
  if (/analys|analyze|research|deep dive/i.test(t)) return '🔍'
  if (/hello|hi|hey|gm|what.*up/i.test(t)) return '👋'
  if (/help|how|what|why|explain/i.test(t)) return '💡'
  // Check for ticker symbols (1-5 uppercase letters)
  if (/\b[A-Z]{1,5}\b/.test(title)) return '📊'
  return '💬'
}

function fmt(t){if(!t)return '';return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`(.+?)`/g,'<code>$1</code>').replace(/\n/g,'<br/>')}
export default App
