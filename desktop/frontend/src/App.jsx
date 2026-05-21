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
  const [loadingText, setLoadingText] = useState('')
  const [account, setAccount] = useState(null)
  const [positions, setPositions] = useState([])
  const [autopilot, setAutopilot] = useState(false)
  const [connected, setConnected] = useState(false)
  const [spyTrend, setSpyTrend] = useState(null)
  const [selectedPos, setSelectedPos] = useState(null)
  const [toasts, setToasts] = useState([])
  const [view, setView] = useState('chat')
  const [perf, setPerf] = useState(null)
  const [showChangelog, setShowChangelog] = useState(() => {
    const v = '2.2'
    const seen = localStorage.getItem('paula-changelog-seen')
    if (seen !== v) return true
    return false
  })
  const dismissChangelog = () => { setShowChangelog(false); localStorage.setItem('paula-changelog-seen', '2.2') }
  
  const [sideOpen, setSideOpen] = useState(window.innerWidth > 768)
  const [pinnedChats, setPinnedChats] = useState(() => {
    try { return JSON.parse(localStorage.getItem('paula-pinned') || '[]') } catch { return [] }
  })
  const togglePin = (id) => {
    const next = pinnedChats.includes(id) ? pinnedChats.filter(x => x !== id) : [...pinnedChats, id]
    setPinnedChats(next)
    localStorage.setItem('paula-pinned', JSON.stringify(next))
  }

  // ── Chat system ──
  const chatsRef = useRef(JSON.parse(localStorage.getItem('paula-chats') || '[]'))
  const [chats, _setChats] = useState(chatsRef.current)
  const chatIdRef = useRef(localStorage.getItem('paula-current-chat') || null)
  const [chatId, _setChatId] = useState(chatIdRef.current)

  const persist = (updated) => {
    chatsRef.current = updated
    _setChats(updated)
    localStorage.setItem('paula-chats', JSON.stringify(updated))
  }

  const setActiveChatId = (id) => {
    chatIdRef.current = id
    _setChatId(id)
    localStorage.setItem('paula-current-chat', id || '')
  }

  // Save current messages into the active chat
  const saveCurrentChat = () => {
    const id = chatIdRef.current
    if (id && messages.length > 0) {
      persist(chatsRef.current.map(c => c.id === id ? { ...c, messages } : c))
    }
  }

  const newChat = () => {
    saveCurrentChat()
    const id = Date.now().toString()
    persist([{ id, title: 'New chat', messages: [], created: new Date().toISOString() }, ...chatsRef.current])
    setActiveChatId(id)
    setMessages([])
    f(API + '/api/chat/clear', { method: 'POST' }).catch(() => {})
  }

  const switchChat = (id) => {
    if (id === chatIdRef.current) return
    saveCurrentChat()
    setActiveChatId(id)
    const chat = chatsRef.current.find(c => c.id === id)
    setMessages(chat?.messages || [])
    f(API + '/api/chat/clear', { method: 'POST' }).catch(() => {})
  }

  const deleteChat = (id) => {
    const updated = chatsRef.current.filter(c => c.id !== id)
    persist(updated)
    if (chatIdRef.current === id) {
      if (updated.length > 0) { setActiveChatId(updated[0].id); setMessages(updated[0].messages || []) }
      else { setActiveChatId(null); setMessages([]) }
    }
  }

  // Auto-save messages when they change (debounced)
  const saveTimer = useRef(null)
  useEffect(() => {
    const id = chatIdRef.current
    if (!id || messages.length === 0) return
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      const updated = chatsRef.current.map(c => c.id === id ? { ...c, messages } : c)
      chatsRef.current = updated
      _setChats(updated)
      localStorage.setItem('paula-chats', JSON.stringify(updated))
    }, 500)
  }, [messages])
  const [settings, setSettings] = useState(() => {
    try { return JSON.parse(localStorage.getItem('paula-settings')) || {} } catch { return {} }
  })
  const settingsRef = useRef(settings)
  useEffect(() => {
    settingsRef.current = settings
    if (settings.accent) document.documentElement.style.setProperty('--grn', settings.accent)
    if (settings.fontSize) document.documentElement.style.setProperty('--chat-fs', settings.fontSize)
  }, [settings])
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
            if (data.status === 'scanned' && data.log && data.log.length > 0) {
              if (settingsRef.current.scanSound !== false) playNotify()
              const summary = data.log.slice(0, 8).join('\n')
              const extra = data.buys || data.sells || data.shorts
                ? `\n\n**Trades:** ${data.buys||0} bought, ${data.sells||0} sold, ${data.shorts||0} shorted`
                : ''
              setMessages(prev => [...prev, {
                role: 'assistant',
                content: `📡 **Scan Complete** — ${data.scanned||'?'} stocks scanned\n\n${summary}${extra}`,
                type: 'autopilot'
              }])
            }
            if (data.status === 'paused' && data.reason) {
              // Only show paused once
              setMessages(prev => {
                const lastAP = [...prev].reverse().find(m => m.type === 'autopilot')
                if (lastAP && lastAP.content.includes('paused')) return prev
                return [...prev, { role: 'assistant', content: `⏸ **Autopilot paused** — ${data.reason}`, type: 'autopilot' }]
              })
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

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') { e.preventDefault(); newChat(); setView('chat') }
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); inputRef.current?.focus() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Ensure a chat exists and return its ID
  const ensureChat = () => {
    const currentId = chatIdRef.current
    const exists = currentId && chatsRef.current.some(c => c.id === currentId)
    if (exists) return currentId

    // Create new chat
    const id = Date.now().toString()
    persist([{ id, title: 'New chat', messages: [], created: new Date().toISOString() }, ...chatsRef.current])
    setActiveChatId(id)
    setMessages([])
    f(API + '/api/chat/clear', { method: 'POST' }).catch(() => {})
    return id
  }

  const sendMessage = async (msg) => {
    if (!msg || sending) return
    setSending(true)
    setInput('')
    setView('chat')
    // Set loading text
    const ml = msg.toLowerCase()
    if (/^analyze |^check |tell me about/i.test(ml)) { const tk = msg.match(/[A-Z]{1,5}/); setLoadingText(tk ? 'Analyzing ' + tk[0] + '...' : 'Analyzing...') }
    else if (/market|regime|spy/i.test(ml)) setLoadingText('Checking market conditions...')
    else if (/buy|sell|short|cover/i.test(ml)) setLoadingText('Executing trade...')
    else if (/gain|mover|top|scan/i.test(ml)) setLoadingText('Scanning market...')
    else if (/recap|today|performance/i.test(ml)) setLoadingText('Loading recap...')
    else setLoadingText('Thinking...')

    // Always ensure chat exists
    const targetId = ensureChat()
    const isFirstMsg = messages.length === 0

    // Show user message immediately
    setMessages(prev => [...prev, { role: 'user', content: msg, time: new Date().toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'}) }])

    try {
      const res = await f(API + '/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      })
      const data = await res.json()

      if (data.ok) {
        const text = data.message || ''
        const words = text.split(/(\s+)/)

        // Start typing animation
        setMessages(prev => [...prev, {
          role: 'assistant', content: '', streaming: true,
          type: data.type, ticker: data.ticker || null,
          tickers: data.tickers || [], signal: data.trade_signal || null,
          time: new Date().toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'})
        }])

        // Reveal words
        let shown = ''
        for (let i = 0; i < words.length; i++) {
          shown += words[i]
          const snap = shown
          setMessages(prev => {
            const m = [...prev]; const last = m[m.length - 1]
            if (last?.streaming) m[m.length - 1] = { ...last, content: snap }
            return m
          })
          if (i % 3 === 0) await new Promise(r => setTimeout(r, 15))
        }

        // Done
        setMessages(prev => {
          const m = [...prev]; const last = m[m.length - 1]
          if (last) m[m.length - 1] = { ...last, streaming: false }
          return m
        })

        // Sounds
        if (data.type === 'trade' && data.message) {
          if (data.message.includes('Bought')) { snd(playBuy); addToast(data.message.slice(0, 60), 'buy') }
          else if (data.message.includes('Sold') || data.message.includes('Shorted')) { snd(playSell); addToast(data.message.slice(0, 60), 'sell') }
          else if (data.message.includes('Covered')) { snd(playProfit); addToast(data.message.slice(0, 60), 'buy') }
        } else { snd(playTick) }

        if (data.autopilot !== undefined) setAutopilot(data.autopilot)
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ ' + (data.error || 'Something went wrong') }])
      }

      // AI title on first message
      if (isFirstMsg) {
        f(API + '/api/chat/title', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }) })
          .then(r => r.json()).then(t => {
            if (t.ok && t.title) persist(chatsRef.current.map(c => c.id === targetId ? { ...c, title: t.title } : c))
          }).catch(() => {
            persist(chatsRef.current.map(c => c.id === targetId && c.title === 'New chat' ? { ...c, title: msg.slice(0, 35) } : c))
          })
      }

      refreshData()
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Connection lost.' }])
    }

    setSending(false)
    setLoadingText('')
    inputRef.current?.focus()
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

      {/* What's New */}
      {showChangelog&&<div className="cl-overlay" onClick={dismissChangelog}>
        <div className="cl-modal" onClick={e=>e.stopPropagation()}>
          <div className="cl-header">
            <span className="cl-badge">v2.2</span>
            <span className="cl-title">What's New</span>
            <button className="cl-close" onClick={dismissChangelog}>×</button>
          </div>
          <div className="cl-body">
            <div className="cl-item"><span className="cl-icon">📌</span><div><b>Pin Chats</b><p>Pin important conversations to the top of the sidebar</p></div></div>
            <div className="cl-item"><span className="cl-icon">⏱️</span><div><b>Timestamps</b><p>See when each message was sent — small time under every bubble</p></div></div>
            <div className="cl-item"><span className="cl-icon">⌨️</span><div><b>Keyboard Shortcuts</b><p>Cmd+N new chat, Cmd+K focus input — power user ready</p></div></div>
            <div className="cl-item"><span className="cl-icon">🎨</span><div><b>Accent Colors</b><p>Pick your color — green, blue, purple, cyan, pink, or orange</p></div></div>
            <div className="cl-item"><span className="cl-icon">📊</span><div><b>Welcome Widgets</b><p>See equity, P&L, positions, and autopilot status at a glance</p></div></div>
            <div className="cl-item"><span className="cl-icon">⚡</span><div><b>Loading States</b><p>Paula tells you what she's doing — "Analyzing AAPL..." not just dots</p></div></div>
            <div className="cl-item"><span className="cl-icon">🧪</span><div><b>Backtest Engine</b><p>Run 90-day historical backtests with equity curve and trade log</p></div></div>
            <div className="cl-item"><span className="cl-icon">⚙️</span><div><b>Settings Overhaul</b><p>API keys, accent colors, font sizes, data export, autopilot control</p></div></div>
          </div>
          <button className="cl-dismiss" onClick={dismissChangelog}>Got it</button>
        </div>
      </div>}

      {/* Sidebar — chats + positions only */}
      <aside className={'sb'+(sideOpen?'':' sb-hide')}>
        <div className="sb-top">
          <div className="sb-logo"><span className="logo-p">P</span>Paula</div>
          <button className="sb-close" onClick={()=>setSideOpen(false)}>×</button>
        </div>
        <button className="new-chat" onClick={newChat}>+ New Chat</button>
        <div className="chat-list">
          {pinnedChats.length > 0 && <div className="cl-section">Pinned</div>}
          {chats.filter(c => pinnedChats.includes(c.id)).map(c => (
            <div key={c.id} className={'chat-item ci-pinned' + (chatId === c.id ? ' ci-active' : '')} onClick={() => {switchChat(c.id);setView('chat')}}>
              <span className="ci-icon">📌</span>
              <span className="ci-title">{c.title}</span>
              <button className="ci-pin" onClick={(e) => { e.stopPropagation(); togglePin(c.id) }} title="Unpin">✕</button>
            </div>
          ))}
          {pinnedChats.length > 0 && chats.filter(c => !pinnedChats.includes(c.id)).length > 0 && <div className="cl-section">Recent</div>}
          {chats.filter(c => !pinnedChats.includes(c.id)).slice(0, 20).map(c => (
            <div key={c.id} className={'chat-item' + (chatId === c.id ? ' ci-active' : '')} onClick={() => {switchChat(c.id);setView('chat')}}>
              <span className="ci-icon">{chatEmoji(c.title)}</span>
              <span className="ci-title">{c.title}</span>
              <div className="ci-acts">
                <button className="ci-pin" onClick={(e) => { e.stopPropagation(); togglePin(c.id) }} title="Pin">📌</button>
                <button className="ci-del" onClick={(e) => { e.stopPropagation(); deleteChat(c.id) }}>×</button>
              </div>
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
            {[['chat','Chat'],['backtest','Backtest'],['stats','Stats'],['settings','Settings']].map(([v,label])=>(
              <button key={v} className={'hdr-tab'+(view===v?' ht-on':'')} onClick={()=>{setView(v);if(v==='stats')loadDashboard()}}>{label}</button>
            ))}
          </nav>
          <div className="hdr-right">
            <button className={'hdr-ap'+(autopilot?' hap-on':'')} onClick={async ()=>{
              const wasOn = autopilot
              setAutopilot(!wasOn)
              newChat()
              const apId = chatIdRef.current
              persist(chatsRef.current.map(c => c.id === apId ? { ...c, title: wasOn ? 'Autopilot Off' : 'Autopilot Session' } : c))
              try {
                const r = await f(API+'/api/autopilot/'+(wasOn?'stop':'start'),{method:'POST'}).then(r=>r.json())
                if (!r.ok) { setAutopilot(wasOn); return }
                setMessages(prev => [...prev, {
                  role: 'assistant',
                  content: wasOn
                    ? '🔴 **Autopilot stopped.**'
                    : '🟢 **Autopilot started.** Scanning every 5 minutes.\n\nLogs will appear here.',
                  type: 'autopilot'
                }])
              } catch { setAutopilot(wasOn) }
              refreshData()
            }}>
              <span className={'ap-dot'+(autopilot?' dot-on':'')}/>{autopilot?'Scanning':'Autopilot'}
            </button>
            <button className="hdr-ver" onClick={()=>setShowChangelog(true)}>v2.2</button>
            <button className="hdr-logout" onClick={logout}>↗</button>
          </div>
        </div>

        {view==='backtest'?<BacktestView/>
        :view==='stats'?<DashView perf={perf}/>
        
        :view==='settings'?<SetView settings={settings} update={updateSetting} user={user} token={token} logout={logout} autopilot={autopilot} setAutopilot={setAutopilot} persist={persist} setActiveChatId={setActiveChatId} setMessages={setMessages} setShowChangelog={setShowChangelog}/>
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
                {account&&<div className="w-widgets">
                  <div className="ww"><span className="ww-n">${account.equity?.toLocaleString(undefined,{maximumFractionDigits:0})}</span><span className="ww-l">Equity</span></div>
                  <div className={'ww'+((account.daily_pnl||0)>=0?' ww-up':' ww-dn')}><span className="ww-n">{(account.daily_pnl||0)>=0?'+':''}{(account.daily_pnl||0).toFixed(0)}</span><span className="ww-l">Today</span></div>
                  <div className="ww"><span className="ww-n">{positions.length}</span><span className="ww-l">Positions</span></div>
                  <div className="ww"><span className={'ww-n '+(autopilot?'up':'')}>{autopilot?'Active':'Off'}</span><span className="ww-l">Autopilot</span></div>
                </div>}
                <div className="w-prompts">
                  {[
                    {q:'Market overview', a:'Check the regime, SPY trend, and whether it\'s safe to trade', cmd:'market regime'},
                    {q:'Top movers', a:'See what\'s running today — biggest gainers with momentum', cmd:'top gainers'},
                    {q:'How did we do today?', a:'Daily P&L recap, trades, and what worked', cmd:'How did we do today?'},
                    {q:'Find me a trade', a:'Scan for setups with the best risk/reward right now', cmd:'What should I buy?'},
                    {q:'Analyze a stock', a:'Deep dive — technicals, score, entry/stop/target', cmd:'Analyze '},
                  ].map((p,i)=>(
                    <button key={i} className="w-prompt" disabled={sending} onClick={()=>{if(p.cmd==='Analyze '){setInput(p.cmd);inputRef.current?.focus()}else sendMessage(p.cmd)}}>
                      <span className="wp-q">{p.q}</span>
                      <span className="wp-a">{p.a}</span>
                    </button>))}
                </div>
              </div>)}
            {messages.map((m,i)=>(
              <div key={i} className={'msg msg-'+m.role}>
                {m.role==='assistant'?(
                  <div className="ai">
                    <div className="ai-av">P</div>
                    <div className="ai-body">
                      <div className="ai-name">Paula</div>
                      <div className="ai-txt"><span dangerouslySetInnerHTML={{__html:fmt(m.content)}}/>{m.streaming&&<span className="stream-cursor">▌</span>}</div>
                      {m.tickers?.length>1?(
                        <ChartTabs tickers={m.tickers} signal={m.signal}/>
                      ):m.ticker||m.tickers?.[0]?(
                        <div className="ai-chart"><Chart ticker={m.ticker||m.tickers[0]} signal={m.signal} height={260}/></div>
                      ):null}
                      {m.time&&!m.streaming&&<div className="msg-time">{m.time}</div>}
                    </div>
                  </div>
                ):(<><div className="user-bubble">{m.content}</div>{m.time&&<div className="msg-time">{m.time}</div>}</>)}
              </div>))}
            {sending&&!messages.some(m=>m.streaming)&&<div className="msg msg-assistant"><div className="ai"><div className="ai-av">P</div><div className="ai-body"><div className="ai-name">Paula</div><div className="loading-state"><div className="dots"><span/><span/><span/></div><span className="loading-txt">{loadingText}</span></div></div></div></div>}
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
function BacktestView() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [mlInsights, setMlInsights] = useState(null)
  const [mlLoading, setMlLoading] = useState(false)

  const runBacktest = async () => {
    setLoading(true)
    try {
      const r = await f(API + '/api/backtest', { method: 'POST' }).then(r => r.json())
      if (r.ok) setResult(r)
    } catch {}
    setLoading(false)
  }

  const runML = async () => {
    setMlLoading(true)
    try {
      const r = await f(API + '/api/ml/train', { method: 'POST' }).then(r => r.json())
      if (r.ok) setMlInsights(r.insights)
    } catch {}
    setMlLoading(false)
  }

  const s = result?.stats
  return (
    <div className="view-scroll">
      <h2 className="view-h">Backtest</h2>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button className="bt-run" onClick={runBacktest} disabled={loading}>
          {loading ? 'Running...' : '▶ Run 90-Day Backtest'}
        </button>
        <button className="bt-run bt-ml" onClick={runML} disabled={mlLoading}>
          {mlLoading ? 'Training...' : '🧠 Analyze Trades'}
        </button>
      </div>

      {!result && !loading && <div className="view-msg">Run a backtest to see how the strategy would have performed on historical data.</div>}

      {s && <>
        {/* Stats grid */}
        <div className="bt-stats">
          <div className="bt-stat"><span className="bt-n">{s.total_trades}</span><span className="bt-l">Trades</span></div>
          <div className="bt-stat"><span className={'bt-n '+(s.win_rate>=50?'up':'dn')}>{s.win_rate}%</span><span className="bt-l">Win Rate</span></div>
          <div className="bt-stat"><span className={'bt-n '+(s.total_pnl>=0?'up':'dn')}>${Math.abs(s.total_pnl).toLocaleString()}</span><span className="bt-l">Total P&L</span></div>
          <div className="bt-stat"><span className={'bt-n '+(s.total_pnl_pct>=0?'up':'dn')}>{s.total_pnl_pct>0?'+':''}{s.total_pnl_pct}%</span><span className="bt-l">Return</span></div>
          <div className="bt-stat"><span className="bt-n">{s.profit_factor}</span><span className="bt-l">Profit Factor</span></div>
          <div className="bt-stat"><span className="bt-n dn">{s.max_drawdown}%</span><span className="bt-l">Max Drawdown</span></div>
          <div className="bt-stat"><span className="bt-n up">${s.avg_win}</span><span className="bt-l">Avg Win</span></div>
          <div className="bt-stat"><span className="bt-n dn">${Math.abs(s.avg_loss)}</span><span className="bt-l">Avg Loss</span></div>
        </div>

        {/* Equity curve */}
        {result.equity_curve?.length > 0 && (
          <div className="card wide" style={{marginTop: 12}}>
            <label>Equity Curve — {s.days} days</label>
            <svg viewBox={`0 0 ${result.equity_curve.length} 100`} className="eq-svg" preserveAspectRatio="none">
              {(() => {
                const pts = result.equity_curve
                const vals = pts.map(p => p.equity)
                const min = Math.min(...vals) * 0.999
                const max = Math.max(...vals) * 1.001
                const range = max - min || 1
                const path = pts.map((p, i) => `${i},${100 - ((p.equity - min) / range) * 90 - 5}`).join(' ')
                const final = pts[pts.length - 1].equity
                const color = final >= s.initial_capital ? '#10b981' : '#ef4444'
                return <>
                  <polyline points={path} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                  <polyline points={`0,${100 - ((s.initial_capital - min) / range) * 90 - 5} ${pts.length},${100 - ((s.initial_capital - min) / range) * 90 - 5}`} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1" strokeDasharray="4" vectorEffect="non-scaling-stroke" />
                </>
              })()}
            </svg>
          </div>
        )}

        {/* Trade log */}
        <div className="card wide" style={{marginTop: 12}}>
          <label>Recent Trades ({result.trades?.length})</label>
          {result.trades?.slice().reverse().slice(0, 20).map((t, i) => (
            <div key={i} className="tr-row">
              <span className={'tr-act ' + (t.pnl >= 0 ? 'up' : 'dn')}>{t.result === 'target' ? 'TP' : 'SL'}</span>
              <span className="tr-sym">{t.ticker}</span>
              <span style={{ fontSize: '.56rem', color: 'var(--dim)', fontFamily: 'var(--mono)' }}>${t.entry}→${t.exit}</span>
              <span className={'tr-time ' + (t.pnl >= 0 ? 'up' : 'dn')} style={{fontWeight: 600}}>{t.pnl >= 0 ? '+' : ''}{t.pnl}</span>
            </div>
          ))}
        </div>
      </>}

      {/* ML Insights */}
      {mlInsights && (
        <div className="card wide" style={{marginTop: 12}}>
          <label>🧠 ML Insights — {mlInsights.total_trades} trades analyzed</label>
          <div className="bt-stats" style={{marginBottom: 12}}>
            <div className="bt-stat"><span className="bt-n">{mlInsights.win_rate}%</span><span className="bt-l">Win Rate</span></div>
            <div className="bt-stat"><span className="bt-n">{mlInsights.avg_winning_score || '—'}</span><span className="bt-l">Avg Win Score</span></div>
            <div className="bt-stat"><span className="bt-n">{mlInsights.avg_losing_score || '—'}</span><span className="bt-l">Avg Loss Score</span></div>
            <div className="bt-stat"><span className="bt-n up">{mlInsights.recommended_min_score || '—'}</span><span className="bt-l">Recommended Min</span></div>
          </div>
          {mlInsights.best_hours && <div style={{fontSize: '.68rem', color: 'var(--dim)', marginBottom: 6}}>Best trading hours: {mlInsights.best_hours.map(h => `${h}:00`).join(', ')}</div>}
          {mlInsights.recommendations?.length > 0 && (
            <div style={{display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8}}>
              {mlInsights.recommendations.map((r, i) => (
                <div key={i} style={{fontSize: '.72rem', color: 'var(--lt)', padding: '8px 12px', background: 'var(--c2)', borderRadius: 8, borderLeft: '3px solid var(--grn)'}}>
                  {r}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ChartTabs({ tickers, signal }) {
  const [active, setActive] = useState(0)
  if (!tickers || !tickers.length) return null
  const safeTicker = tickers[Math.min(active, tickers.length - 1)]
  return (
    <div className="ai-chart">
      <div className="ct-tabs">
        {tickers.map((t, i) => (
          <button key={t} className={'ct-tab' + (i === active ? ' ct-on' : '')} onClick={() => setActive(i)}>{t}</button>
        ))}
      </div>
      <Chart key={safeTicker} ticker={safeTicker} signal={active === 0 ? signal : null} height={240} />
    </div>
  )
}

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

function SetView({settings,update,user,token,logout,autopilot,setAutopilot,persist,setActiveChatId,setMessages,setShowChangelog}){
  const [keys, setKeys] = useState({alpaca_key:'',alpaca_secret:'',groq_key:'',polygon_key:''})
  const [keySaved, setKeySaved] = useState(false)
  const [keyLoaded, setKeyLoaded] = useState(false)

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

  const accentColors = [
    {name:'Green',val:'#10b981'},{name:'Blue',val:'#3b82f6'},{name:'Purple',val:'#8b5cf6'},
    {name:'Cyan',val:'#06b6d4'},{name:'Pink',val:'#ec4899'},{name:'Orange',val:'#f59e0b'},
  ]

  const fontSizes = [{name:'Small',val:'13px'},{name:'Default',val:'15px'},{name:'Large',val:'17px'}]

  return(<div className="view-scroll"><h2 className="view-h">Settings</h2>

    {/* Account */}
    {user&&<div className="card wide"><label>Account</label>
      <div className="s-row"><span>Username</span><span className="s-user">{user.username}</span></div>
      <div className="s-row"><span>Display name</span><input className="s-inp" value={settings.userName||user?.username||''} onChange={e=>update('userName',e.target.value)} placeholder="Your name"/></div>
    </div>}

    {/* API Keys */}
    {user&&<div className="card wide"><label>API Keys</label>
      <div className="s-row"><span>Alpaca Key</span><input className="s-inp s-wide" type="password" autoComplete="off" value={keys.alpaca_key} onChange={e=>setKeys({...keys,alpaca_key:e.target.value})} placeholder="PKSPW..."/></div>
      <div className="s-row"><span>Alpaca Secret</span><input className="s-inp s-wide" type="password" autoComplete="off" value={keys.alpaca_secret} onChange={e=>setKeys({...keys,alpaca_secret:e.target.value})} placeholder="AzMr..."/></div>
      <div className="s-row"><span>Groq Key</span><input className="s-inp s-wide" type="password" autoComplete="off" value={keys.groq_key} onChange={e=>setKeys({...keys,groq_key:e.target.value})} placeholder="gsk_..."/></div>
      <div className="s-row"><span>Polygon Key</span><input className="s-inp s-wide" type="password" autoComplete="off" value={keys.polygon_key} onChange={e=>setKeys({...keys,polygon_key:e.target.value})} placeholder="wzJ5..."/></div>
      <button className={'login-btn s-save'+(keySaved?' s-saved':'')} onClick={saveKeys}>{keySaved?'✓ Saved':'Save Keys'}</button>
    </div>}

    {/* Appearance */}
    <div className="card wide"><label>Appearance</label>
      <div className="s-row"><span>Accent Color</span>
        <div className="color-picks">
          {accentColors.map(c=>(
            <button key={c.val} className={'color-dot'+(settings.accent===c.val||(!settings.accent&&c.val==='#10b981')?' cd-on':'')}
              style={{background:c.val}} onClick={()=>{update('accent',c.val);document.documentElement.style.setProperty('--grn',c.val)}} title={c.name}/>
          ))}
        </div>
      </div>
      <div className="s-row"><span>Font Size</span>
        <div className="font-picks">
          {fontSizes.map(s=>(
            <button key={s.val} className={'fp-btn'+(settings.fontSize===s.val||(!settings.fontSize&&s.val==='15px')?' fp-on':'')}
              onClick={()=>{update('fontSize',s.val);document.documentElement.style.setProperty('--chat-fs',s.val)}}>{s.name}</button>
          ))}
        </div>
      </div>
    </div>

    {/* Sounds */}
    <div className="card wide"><label>Sounds</label>
      <Tog l="Trade sounds" on={settings.sounds!==false} fn={()=>update('sounds',!(settings.sounds!==false))}/>
      <Tog l="Scan notification" on={settings.scanSound!==false} fn={()=>update('scanSound',!(settings.scanSound!==false))}/>
    </div>

    {/* Notifications */}
    <div className="card wide"><label>Notifications</label>
      <Tog l="Toast popups" on={settings.toasts!==false} fn={()=>update('toasts',!(settings.toasts!==false))}/>
      <Tog l="Phone notifications" on={settings.pushNotif!==false} fn={()=>update('pushNotif',!(settings.pushNotif!==false))}/>
    </div>

    {/* Autopilot */}
    <div className="card wide"><label>Autopilot</label>
      <div className="s-row"><span>Status</span><span className={'s-status'+(autopilot?' s-on':'')}>{autopilot?'Scanning':'Off'}</span></div>
      <div className="s-row"><span>Auto-scan</span>
        <button className={'toggle-sw'+(autopilot?' sw-on':'')} onClick={async ()=>{
          const wasOn = autopilot; setAutopilot(!wasOn)
          try { await f(API+'/api/autopilot/'+(wasOn?'stop':'start'),{method:'POST'}) } catch { setAutopilot(wasOn) }
        }} role="switch" aria-checked={autopilot}><span className="sw-thumb"/></button>
      </div>
    </div>

    {/* Data */}
    <div className="card wide"><label>Data</label>
      <div className="s-row"><span>Clear all chats</span><button className="tog tog-danger" onClick={()=>{
        if(confirm('Delete all chats? This cannot be undone.')){persist([]);setActiveChatId(null);setMessages([])}
      }}>Clear</button></div>
      <div className="s-row"><span>Export trade log</span><button className="tog" onClick={async ()=>{
        try{const r=await f(API+'/api/trades').then(r=>r.json());if(r.ok){const b=new Blob([JSON.stringify(r.data,null,2)],{type:'application/json'});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download='paula-trades.json';a.click()}}catch{}
      }}>Export</button></div>
    </div>

    {/* About */}
    <div className="card wide"><label>About</label>
      <div className="s-row"><span>Version</span><span className="s-ver">v2.2</span></div>
      <div className="s-row"><span>What's new</span><button className="tog" onClick={()=>setShowChangelog(true)}>View</button></div>
      <div className="s-row"><span>Sign out</span><button className="tog tog-danger" onClick={logout}>Logout</button></div>
    </div>
  </div>)
}

function Tog({l,on,fn}){return <div className="s-row"><span>{l}</span><button className={'toggle-sw'+(on?' sw-on':'')} onClick={fn} role="switch" aria-checked={on}><span className="sw-thumb"/></button></div>}

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
