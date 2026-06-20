import { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react'
const Chart = lazy(() => import('./Chart'))
const ChartFallback = () => <div className="chart-loading"><div className="chart-shimmer"/></div>
import { playBuy, playSell, playNotify, playAlert, playProfit, playTick } from './sounds'
import './App.css'

// Backend URL resolution:
//  1. VITE_API_URL (set this to your ngrok/Railway URL when hosting) — wins always
//  2. localhost dev fallback when running the app on your own machine
//  3. otherwise: same origin as the page (works if frontend+backend share a host)
const _envApi = import.meta.env.VITE_API_URL
const BACKEND = (
  _envApi
    ? _envApi
    : (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
      ? 'http://127.0.0.1:3141'
      : window.location.origin
).replace(/\/+$/, '')
const API = BACKEND
// ── Version: bump this on every shipped change (semver: major.minor.patch) ──
// patch = fix, minor = feature, major = big release. Shown in the header, the
// settings About row, and the "What's new" modal.
const VERSION = '3.17.1'
const VERSION_DATE = 'June 18, 2026'
// Full version history for the scrollable "What's new" modal — newest first.
// Add a new entry at the TOP whenever VERSION bumps.
const CHANGELOG_DATA = [
  { v: '3.17.1', d: 'June 18, 2026', changes: [
    'Fixed the mobile layout \u2014 the sidebar is now a proper slide-in menu (tap the \u2630 to open, tap outside to close) instead of a stuck strip of icons, and content fills the screen.',
  ]},
  { v: '3.17.0', d: 'June 18, 2026', changes: [
    'Faster first load \u2014 the charting code now loads only when a chart is shown, cutting the initial download roughly in half.',
    'Less battery + data use \u2014 Paula pauses background refreshing when the tab isn\u2019t visible, and the login ticker is cached.',
  ]},
  { v: '3.16.4', d: 'June 18, 2026', changes: [
    'Nicer loading screen \u2014 an animated logo, the Paula wordmark, and a progress shimmer instead of a bare black screen.',
  ]},
  { v: '3.16.3', d: 'June 18, 2026', changes: [
    'Small fixes: corrected a few theme color variables, and position sizing now explains clearly when your risk budget is too small for even one share.',
  ]},
  { v: '3.16.2', d: 'June 18, 2026', changes: [
    'Light theme now covers the sidebar too, with a smooth color fade when you switch themes.',
  ]},
  { v: '3.16.1', d: 'June 18, 2026', changes: [
    'Fixed compare/earnings/position-sizing not working with lowercase tickers (e.g. "compare tsla and nvda").',
  ]},
  { v: '3.16.0', d: 'June 17, 2026', changes: [
    'Annual Paula Plus \u2014 $99/year (2 months free) alongside the $9.99/mo plan.',
    'A dedicated Plus page with full plan comparison, reachable from Settings.',
  ]},
  { v: '3.15.0', d: 'June 17, 2026', changes: [
    'Light theme — switch between dark and light in Settings \u2192 Appearance. Your choice is remembered.',
  ]},
  { v: '3.14.0', d: 'June 17, 2026', changes: [
    'Earnings calendar — ask "when does NVDA report earnings" and Paula tells you the date, how soon it is, and warns if it\u2019s close.',
  ]},
  { v: '3.13.0', d: 'June 17, 2026', changes: [
    'The "What\u2019s new" history is now collapsible — tap any version to expand its changes, with the date shown next to each version.',
  ]},
  { v: '3.12.0', d: 'June 17, 2026', changes: [
    'Position sizing — ask "how many shares of NVDA if I risk $200" and Paula calculates the share count from the stop distance.',
  ]},
  { v: '3.11.0', d: 'June 17, 2026', changes: [
    'Autopilot trailing stops — once a position is up ~3%, the stop ratchets up to lock in gains (and never moves back down).',
  ]},
  { v: '3.10.0', d: 'June 17, 2026', changes: [
    'Compare two stocks head-to-head — ask "NVDA vs AMD" or "should I buy TSLA or RIVN" and Paula scores both and picks a winner.',
  ]},
  { v: '3.9.8', d: 'June 16, 2026', changes: [
    'The "What\u2019s new" screen is now a full scrollable history \u2014 every version, its date, and what changed.',
  ]},
  { v: '3.9.6', d: 'June 16, 2026', changes: [
    'New "Hey Paula — for everything trading" branding on the trailer and login.',
    'Free tier is a clean 5 messages per day.',
  ]},
  { v: '3.9.0', d: 'June 15, 2026', changes: [
    'Introducing Paula Plus ($9.99/mo): unlimited messages, unlimited chats, and full access.',
    'Free tier: 5 messages a day, one chat, with Analyze & Portfolio reserved for Plus.',
    'Smooth upgrade flow with an unlock celebration.',
    'Admins can grant or revoke Plus from the admin panel.',
  ]},
  { v: '3.8.0', d: 'June 14, 2026', changes: [
    'Maintenance mode — a clean full-screen notice when Paula is getting an upgrade.',
    '"Look it up" now actually searches the web for current info.',
    'Trade levels never collapse — entry, stop, and target are always distinct.',
    'Smoother chat scrolling that no longer fights you while a reply streams in.',
  ]},
  { v: '3.7.0', d: 'June 13, 2026', changes: [
    'Portfolio-aware advice — ask about adding to or trimming a position and Paula factors in your real buying power, holdings, and risk.',
    'Sharper understanding of what you actually asked.',
  ]},
  { v: '3.5.0', d: 'June 11, 2026', changes: [
    'Per-account trading — connect your own Alpaca keys and Paula trades your account (encrypted, private to you).',
    'Your win rate and recent trades inform Paula\u2019s advice.',
  ]},
  { v: '3.4.0', d: 'June 10, 2026', changes: [
    'Autopilot now scans a much wider universe — hundreds of names per cycle via fast batch fetching.',
  ]},
  { v: '3.3.0', d: 'June 8, 2026', changes: [
    'Scanner widened to 1,000+ liquid stocks, plus a full-NYSE mode.',
    'Themed scans: energy, defense, biotech, crypto, value.',
    'Delisted, acquired, and brand-new IPO stocks filtered out — no fake scores.',
    'Redesigned welcome screen and Analyze view; new hover navigation rail.',
    'Real market data on login; live intraday (1D/5D) charts.',
  ]},
  { v: '3.2.0', d: 'May 28, 2026', changes: [
    'Named setups — every pick comes with its thesis (pullback, breakout, oversold bounce, coiling).',
    '52-week-high & VCP detection; honest multi-position backtest.',
    'True swing trading — positions held overnight, no end-of-day force-close.',
    'Live news, web search, market-hours awareness.',
  ]},
  { v: '3.1.0', d: 'May 20, 2026', changes: [
    'Per-chat memory — each conversation stays its own.',
    'Stop a reply mid-stream; always-on cloud hosting.',
    'Consistent scores between Analyze and chat.',
  ]},
  { v: '3.0.0', d: 'May 12, 2026', changes: [
    'Paula reborn as a desktop app — a full swing-trading copilot.',
    'Multi-factor scoring engine: RSI, MACD, Bollinger Bands, ATR, momentum, fundamentals.',
    'Alpaca paper trading, AI news analysis, and an autopilot that trades for you.',
  ]},
]
const ADMIN_EMAIL = 'parjan.d@icloud.com'
// Email-dependent auth (2FA, signup verification, password reset) is OFF until a
// sending domain is verified in Resend. Keep in sync with the backend's
// EMAIL_AUTH_ENABLED. Flip to true when email works.
const EMAIL_AUTH = false
try {
  console.log('[Paula] Using backend:', BACKEND, '| page host:', window.location.hostname)
  if (!_envApi && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    console.warn('[Paula] VITE_API_URL is not set — falling back to page origin. Set VITE_API_URL to your backend URL (ngrok/Railway) when hosting.')
  }
} catch {}
const H = { 'ngrok-skip-browser-warning': '1' }
const f = (url, opts = {}) => {
  const headers = { ...H, ...(opts.headers || {}) }
  const tk = localStorage.getItem('paula-token')
  if (tk) headers['Authorization'] = 'Bearer ' + tk
  return fetch(url, { ...opts, headers })
}
const WS_URL = `${BACKEND.startsWith('https') ? 'wss:' : 'ws:'}//${new URL(BACKEND).host}/ws`

function ChangelogRelease({ rel, defaultOpen, latest }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={"cl-release" + (open ? " cl-open" : "")}>
      <button className="cl-rel-head" onClick={() => setOpen(o => !o)}>
        <span className={"cl-rel-ver" + (latest ? " cl-rel-latest" : "")}>
          v{rel.v}{latest && <span className="cl-rel-tag">Latest</span>}
        </span>
        <span className="cl-rel-date">{rel.d}</span>
        <svg className="cl-rel-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M6 9l6 6 6-6"/></svg>
      </button>
      {open && <ul className="cl-rel-list">
        {rel.changes.map((c, j) => (
          <li className="cl-rel-item" key={j}><span className="cl-dot cl-dot-grn"/><span>{c}</span></li>
        ))}
      </ul>}
    </div>
  )
}

function App() {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('paula-token'))
  const [authLoading, setAuthLoading] = useState(true)
  const [maint, setMaint] = useState({ on: false, message: '' })
  const [theme, setTheme] = useState(() => localStorage.getItem('paula-theme') || 'dark')

  // Apply the theme to the document root and persist it.
  useEffect(() => {
    if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light')
    else document.documentElement.removeAttribute('data-theme')
    localStorage.setItem('paula-theme', theme)
  }, [theme])

  // Poll maintenance status (everyone sees it; admin is exempt from the block).
  useEffect(() => {
    let alive = true
    const check = () => f(API + '/api/maintenance').then(r => r.json()).then(d => { if (alive && d.ok) setMaint({ on: d.on, message: d.message || '' }) }).catch(() => {})
    check()
    const id = setInterval(() => { if (!document.hidden) check() }, 30000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  // Check auth on mount
  useEffect(() => {
    if (token) {
      f(API + '/api/auth/me', { headers: { 'Authorization': 'Bearer ' + token } })
        .then(r => r.json())
        .then(async data => {
          if (data.ok) {
            setUser({ ...data.user, plus: !!data.plus, is_admin: !!data.is_admin })
          } else { setToken(null); localStorage.removeItem('paula-token') }
        })
        .catch(() => {})
        .finally(() => setAuthLoading(false))
    } else { setAuthLoading(false) }
  }, [token])

  const doAuth = async (username, password, isSignup, email) => {
    const res = await f(API + '/api/auth/' + (isSignup ? 'signup' : 'login'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: isSignup ? username : undefined, password, email: isSignup ? email : username })
    }).then(r => r.json())
    // 2FA / email verification: a code was emailed; don't log in yet — the
    // LoginPage will collect the code and call finishAuth() below.
    if (res.ok && (res.needs_2fa || res.needs_verification)) return res
    if (res.ok && res.token) {
      setToken(res.token); setUser(res.user); localStorage.setItem('paula-token', res.token)
      const settingsKey = 'paula-settings-' + res.user.id
      const s = JSON.parse(localStorage.getItem(settingsKey) || '{}')
      if (!s.userName) { s.userName = res.user.username; localStorage.setItem(settingsKey, JSON.stringify(s)) }
    }
    return res
  }

  // Called after a 2FA code verifies — completes the session with the issued token.
  const finishAuth = (res) => {
    if (res.ok && res.token) {
      setToken(res.token); setUser(res.user); localStorage.setItem('paula-token', res.token)
      const settingsKey = 'paula-settings-' + res.user.id
      const s = JSON.parse(localStorage.getItem(settingsKey) || '{}')
      if (!s.userName) { s.userName = res.user.username; localStorage.setItem(settingsKey, JSON.stringify(s)) }
    }
  }

  const logout = () => { setUser(null); setToken(null); localStorage.removeItem('paula-token') }

  if (authLoading) return (
    <div className="auth-loading">
      <div className="al-glow" />
      <div className="al-inner">
        <div className="al-logo">P</div>
        <div className="al-name">Paula</div>
        <div className="al-bar"><span /></div>
      </div>
    </div>
  )
  // Maintenance mode: block everyone except the admin account.
  if (maint.on && (!user || (user.email || '').toLowerCase() !== ADMIN_EMAIL)) {
    return <div className="maint-screen">
      <div className="maint-card">
        <div className="maint-logo">P</div>
        <h1>Down for maintenance</h1>
        <p>{maint.message || "Paula is getting an upgrade. We'll be back shortly — thanks for your patience."}</p>
        <div className="maint-pulse"><span></span><span></span><span></span></div>
      </div>
    </div>
  }
  if (!user) return <LoginPage onAuth={doAuth} onFinishAuth={finishAuth} />


  return <MainApp user={user} token={token} logout={logout} setUser={setUser} theme={theme} setTheme={setTheme} />
}

function LoginPage({ onAuth, onFinishAuth }) {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [isSignup, setIsSignup] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  // 2FA / email-verification code step
  const [codeStep, setCodeStep] = useState(null) // null | '2fa' | 'verify'
  const [code, setCode] = useState('')
  const [codeEmail, setCodeEmail] = useState('')
  // Password reset
  const resetToken = (() => { try { return new URLSearchParams(window.location.search).get('reset') } catch { return null } })()
  const [view, setView] = useState(resetToken ? 'reset' : 'auth') // 'auth' | 'forgot' | 'reset'
  const [notice, setNotice] = useState('')
  const [newPw, setNewPw] = useState('')

  const FALLBACK_TAPE = ['NVDA','AAPL','MSFT','GOOGL','AMZN','META','TSLA','AVGO','AMD','XOM','JPM','NFLX','SPY','QQQ','COST']
  const [tape, setTape] = useState(FALLBACK_TAPE.map(s => ({ sym: s, pct: null })))
  useEffect(() => {
    let alive = true
    fetch(API + '/api/tape').then(r => r.json()).then(d => {
      if (alive && d.ok && d.tape && d.tape.length) setTape(d.tape)
    }).catch(() => {})
    return () => { alive = false }
  }, [])

  const submit = async (e) => {
    e?.preventDefault()
    let nameToUse = username
    if (isSignup) {
      if (!email || !password) { setError('Email and password are required'); return }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError('Enter a valid email address'); return }
      if (password.length < 6) { setError('Password must be at least 6 characters'); return }
      // Display name is optional — default to the part of the email before the @.
      if (!username.trim()) { nameToUse = email.split('@')[0]; setUsername(nameToUse) }
    } else {
      if (!username || !password) { setError('Email and password required'); return }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(username)) { setError('Enter a valid email address'); return }
    }
    setLoading(true); setError('')
    const res = await onAuth(nameToUse, password, isSignup, email)
    if (!res.ok) { setError(res.error); setLoading(false); return }
    if (res.needs_2fa) { setCodeStep('2fa'); setCodeEmail(res.email); setError(''); setLoading(false); return }
    if (res.needs_verification) { setCodeStep('verify'); setCodeEmail(res.email || email); setError(''); setLoading(false); return }
    setLoading(false)
  }

  const submitCode = async (e) => {
    e?.preventDefault()
    if (!/^\d{6}$/.test(code.trim())) { setError('Enter the 6-digit code'); return }
    setLoading(true); setError('')
    try {
      const r = await f(API + '/api/auth/verify-code', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: codeEmail, password: code.trim(), username: codeStep })
      }).then(r => r.json())
      if (!r.ok) { setError(r.error || 'Invalid code'); setLoading(false); return }
      if (codeStep === '2fa') {
        onFinishAuth(r)  // r has the real token now
      } else {
        // email verified on signup — drop back to login so they can sign in
        setCodeStep(null); setCode(''); setIsSignup(false)
        setError(''); setNotice && setNotice('Email verified — sign in to continue.')
      }
    } catch { setError("Can't connect to backend") }
    setLoading(false)
  }

  const resendCode = async () => {
    setError(''); setNotice && setNotice('')
    try {
      await f(API + '/api/auth/resend-code', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: codeEmail, username: codeStep })
      })
      setNotice && setNotice('A new code has been sent.')
    } catch { setError("Can't connect to backend") }
  }

  const submitForgot = async (e) => {
    e?.preventDefault()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError('Enter a valid email address'); return }
    setLoading(true); setError(''); setNotice('')
    try {
      const r = await f(API + '/api/auth/forgot', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) }).then(r => r.json())
      setNotice(r.message || 'If an account exists for that email, a reset link has been sent.')
    } catch { setError("Can't connect to backend") }
    setLoading(false)
  }

  const submitReset = async (e) => {
    e?.preventDefault()
    if (newPw.length < 6) { setError('Password must be at least 6 characters'); return }
    setLoading(true); setError(''); setNotice('')
    try {
      const r = await f(API + '/api/auth/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: resetToken, password: newPw }) }).then(r => r.json())
      if (r.ok) {
        setNotice('Password updated. You can sign in now.')
        setView('auth'); setIsSignup(false)
        try { window.history.replaceState({}, '', window.location.pathname) } catch {}
      } else { setError(r.error || 'Reset failed') }
    } catch { setError("Can't connect to backend") }
    setLoading(false)
  }

  const fmtTape = (t) => t.pct == null ? t.sym : `${t.sym} ${t.pct >= 0 ? '+' : '−'}${Math.abs(t.pct)}%`
  const tapeIsDown = (t) => t.pct != null && t.pct < 0

  return (
    <div className="lg-root">
      {/* Living terminal background — tape + breathing equity curve, behind everything */}
      <div className="lg-bg" aria-hidden="true">
        <div className="lg-tape lg-tape-1">{[...tape, ...tape].map((t, i) => <span key={i} className={'lg-tick' + (tapeIsDown(t) ? ' dn' : ' up')}>{fmtTape(t)}</span>)}</div>
        <div className="lg-tape lg-tape-2">{[...tape, ...tape].map((t, i) => <span key={i} className={'lg-tick' + (tapeIsDown(t) ? ' dn' : ' up')}>{fmtTape(t)}</span>)}</div>
        <svg className="lg-curve" viewBox="0 0 1000 600" preserveAspectRatio="none">
          <defs><linearGradient id="lgGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#10b981" stopOpacity="0.18"/><stop offset="100%" stopColor="#10b981" stopOpacity="0"/></linearGradient></defs>
          <polyline points="0,470 100,450 200,460 300,400 400,420 500,340 600,365 700,280 800,305 900,215 1000,185" fill="none" stroke="#10b981" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
          <polygon points="0,470 100,450 200,460 300,400 400,420 500,340 600,365 700,280 800,305 900,215 1000,185 1000,600 0,600" fill="url(#lgGrad)"/>
        </svg>
      </div>

      <div className="lg-grid">
        {/* Left — the statement */}
        <div className="lg-left">
          <div className="lg-brand"><span className="logo-p">P</span><span className="lg-brand-name">Paula</span></div>
          <div className="lg-statement">
            <h1 className="lg-hero">Markets don't<br/>sleep.<br/><span className="lg-hero-grn">Neither does<br/>Paula.</span></h1>
            <p className="lg-tagline">Hey Paula — for everything trading. She finds the setups, holds for the move, and watches the tape so you don't have to.</p>
            <div className="lg-pills">
              <span className="lg-pill">Named setups</span>
              <span className="lg-pill">Live news</span>
              <span className="lg-pill">Autopilot</span>
              <span className="lg-pill">Always-on</span>
            </div>
          </div>
          <div className="lg-spacer" aria-hidden="true"></div>
        </div>

        {/* Right — the form, in a frosted card */}
        <div className="lg-right">
          <div className="lg-card">
            {view === 'auth' && codeStep && <>
              <h2 className="lg-card-title">{codeStep === '2fa' ? 'Verify it\u2019s you' : 'Verify your email'}</h2>
              <p className="lg-card-sub">We sent a 6-digit code to <b>{codeEmail}</b>. Enter it below{codeStep === '2fa' ? ' to finish signing in.' : ' to verify your account.'}</p>
              <div className="lg-form">
                <label className="lg-label">6-digit code</label>
                <input className="lg-input lg-code" inputMode="numeric" maxLength={6} value={code} autoFocus
                  onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  onKeyDown={e => { if (e.key === 'Enter') submitCode() }} />
                {error && <div className="lg-error">{error}</div>}
                {notice && <div className="lg-notice">{notice}</div>}
                <button className="lg-btn" onClick={submitCode} disabled={loading}>{loading ? '…' : 'Verify →'}</button>
                <button className="lg-toggle" onClick={resendCode}>Didn't get it? <span className="lg-link">Resend code</span></button>
                <button className="lg-toggle" onClick={() => { setCodeStep(null); setCode(''); setError(''); setNotice('') }}><span className="lg-link">← Back</span></button>
              </div>
            </>}

            {view === 'auth' && !codeStep && <>
              <h2 className="lg-card-title">{isSignup ? 'Create account' : 'Welcome back'}</h2>
              <p className="lg-card-sub">{isSignup ? "Takes 30 seconds. No card required for paper trading." : "The market's moving. Let's get to work."}</p>
              <div className="lg-form">
                {isSignup && <>
                  <label className="lg-label">Email</label>
                  <input className="lg-input lg-email" name="paula-email" autoComplete="off" data-1p-ignore data-lpignore="true" type="email" inputMode="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') document.querySelector('.lg-pw')?.focus() }} autoFocus />
                  <label className="lg-label">Display name <span className="lg-opt">(optional)</span></label>
                  <input className="lg-input" name="paula-name" autoComplete="off" data-1p-ignore data-lpignore="true" placeholder="What should Paula call you?" value={username} onChange={e => setUsername(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') document.querySelector('.lg-pw')?.focus() }} />
                </>}
                {!isSignup && <>
                  <label className="lg-label">Email</label>
                  <input className="lg-input" name="paula-email" autoComplete="off" data-1p-ignore data-lpignore="true" type="email" inputMode="email" placeholder="you@example.com" value={username} onChange={e => setUsername(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') document.querySelector('.lg-pw')?.focus() }} autoFocus />
                </>}
                <div className="lg-pw-row">
                  <label className="lg-label">Password</label>
                  {!isSignup && EMAIL_AUTH && <button type="button" className="lg-forgot" onClick={() => { setView('forgot'); setError(''); setNotice(''); setEmail(username) }}>Forgot?</button>}
                </div>
                <div className="lg-pw-wrap">
                  <input className="lg-input lg-pw" type={showPw ? 'text' : 'password'} placeholder={isSignup ? 'At least 6 characters' : 'Your password'} autoComplete={isSignup ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') submit() }} />
                  <button type="button" className="lg-eye" onClick={() => setShowPw(!showPw)} aria-label={showPw ? 'Hide password' : 'Show password'}>{showPw ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg> : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>}</button>
                </div>
                {error && <div className="lg-error">{error}</div>}
                {notice && <div className="lg-notice">{notice}</div>}
                <button className="lg-btn" onClick={submit} disabled={loading}>{loading ? '…' : isSignup ? 'Create account →' : 'Sign in →'}</button>
                <button className="lg-toggle" onClick={() => {
                  setError(''); setNotice('')
                  if (!isSignup) { setEmail(username); setUsername('') } else { setUsername(email) }
                  setIsSignup(!isSignup)
                }}>{isSignup ? 'Already have an account? ' : 'New to Paula? '}<span className="lg-link">{isSignup ? 'Sign in' : 'Create account'}</span></button>
              </div>
            </>}

            {view === 'forgot' && <>
              <h2 className="lg-card-title">Reset your password</h2>
              <p className="lg-card-sub">Enter your account email and we'll send a reset link.</p>
              <div className="lg-form">
                <label className="lg-label">Email</label>
                <input className="lg-input" type="email" autoComplete="off" value={email} onChange={e => setEmail(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') submitForgot() }} autoFocus />
                {error && <div className="lg-error">{error}</div>}
                {notice && <div className="lg-notice">{notice}</div>}
                <button className="lg-btn" onClick={submitForgot} disabled={loading}>{loading ? '…' : 'Send reset link →'}</button>
                <button className="lg-toggle" onClick={() => { setView('auth'); setError(''); setNotice('') }}><span className="lg-link">Back to sign in</span></button>
              </div>
            </>}

            {view === 'reset' && <>
              <h2 className="lg-card-title">Set a new password</h2>
              <p className="lg-card-sub">Choose a new password for your account.</p>
              <div className="lg-form">
                <label className="lg-label">New password</label>
                <div className="lg-pw-wrap">
                  <input className="lg-input lg-pw" type={showPw ? 'text' : 'password'} autoComplete="new-password" value={newPw} onChange={e => setNewPw(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') submitReset() }} autoFocus />
                  <button type="button" className="lg-eye" onClick={() => setShowPw(!showPw)} aria-label={showPw ? 'Hide password' : 'Show password'}>{showPw ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg> : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>}</button>
                </div>
                {error && <div className="lg-error">{error}</div>}
                {notice && <div className="lg-notice">{notice}</div>}
                <button className="lg-btn" onClick={submitReset} disabled={loading}>{loading ? '…' : 'Update password →'}</button>
                <button className="lg-toggle" onClick={() => { setView('auth'); setError(''); setNotice(''); try { window.history.replaceState({}, '', window.location.pathname) } catch {} }}><span className="lg-link">Back to sign in</span></button>
              </div>
            </>}

            <div className="lg-footer">By continuing you agree to our Terms · Privacy</div>
            <a href="/commercial.html" target="_blank" className="lg-trailer">▶ Watch the trailer</a>
          </div>
        </div>
      </div>
    </div>
  )
}

function OnboardingPage({ user, onComplete, onSkip }) {
  const [risk, setRisk] = useState('1.0%')
  const style = 'Swing'        // Paula is a swing trader — not a choice
  const bias = 'Auto'          // Paula reads market direction itself — not a choice

  const finish = () => onComplete(style, bias, risk)

  return (
    <div className="cl-overlay">
      <div className="cl-modal" onClick={e => e.stopPropagation()} style={{width: 460}}>
        <div className="ob-progress-track">
          <div className="ob-progress-fill" style={{width: '100%'}}/>
        </div>

        <div className="cl-pad" style={{padding: '28px 28px 24px'}}>
          <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:20}}>
            <span className="logo-p" style={{width:28,height:28,fontSize:12}}>P</span>
            <span style={{fontWeight:600,color:'var(--wh)',fontSize:'.88rem'}}>Quick setup</span>
          </div>

          <h3 className="ob-h">One quick thing</h3>
          <p className="ob-sub">Paula is a swing-trading copilot — she finds quality setups, reads the market direction herself, and holds for days. Just pick how much you want to risk per trade.</p>
          <div className="ob-opts ob-opts-3">
            {[{v:'0.5%',d:'Conservative'},{v:'1.0%',d:'Standard'},{v:'2.0%',d:'Aggressive'}].map(s => (
              <button key={s.v} className={'fp-btn ob-opt'+(risk===s.v?' fp-on':'')} onClick={() => setRisk(s.v)}>
                <span className="ob-opt-title">{s.v}</span>
                <span className="ob-opt-desc">{s.d}</span>
              </button>
            ))}
          </div>
          <button className="login-btn" onClick={finish}>Start trading</button>

          <button className="onboard-skip" onClick={onSkip}>Skip setup</button>
        </div>
      </div>
    </div>
  )
}

function PlusPage({ isPlus, onBuy, setView }) {
  return (
    <div className="plus-page">
      <div className="plus-page-inner">
        <div className="plus-badge plus-page-badge">PAULA <span>PLUS</span></div>
        <h1 className="plus-page-title">{isPlus ? "You're on Paula Plus" : "Trade with everything unlocked"}</h1>
        <p className="plus-page-sub">{isPlus ? "Thanks for being a Plus member — everything's unlocked for you." : "Unlimited access to every part of Paula, for less than a coffee a week."}</p>

        {!isPlus && <div className="plus-page-cards">
          <div className="plus-page-card">
            <div className="ppc-name">Monthly</div>
            <div className="ppc-price">$9.99<span>/mo</span></div>
            <div className="ppc-note">Billed monthly</div>
          </div>
          <div className="plus-page-card ppc-feature">
            <div className="ppc-tag">Best value · 2 months free</div>
            <div className="ppc-name">Annual</div>
            <div className="ppc-price">$99<span>/yr</span></div>
            <div className="ppc-note">Works out to $8.25/mo</div>
          </div>
        </div>}

        <div className="plus-page-feats">
          {[
            ['Unlimited messages', 'No daily cap — ask Paula as much as you want.'],
            ['Unlimited chats', 'Organize your trades and ideas across as many chats as you like.'],
            ['Full Analyze', 'Deep dives, company breakdowns, and the full signal picture on any stock.'],
            ['Everything, unlocked', 'Every feature Paula has, with no limits.'],
          ].map(([t, d], i) => (
            <div className="ppf" key={i}><span className="cl-dot cl-dot-grn"/><div><b>{t}</b><p>{d}</p></div></div>
          ))}
        </div>

        {!isPlus
          ? <button className="plus-buy plus-page-cta" onClick={onBuy}>Choose a plan →</button>
          : <button className="plus-cancel" onClick={() => setView('chat')}>Back to Paula</button>}
      </div>
    </div>
  )
}

function PlusModal({ token, onClose, onUnlocked }) {
  const [stage, setStage] = useState('offer') // offer | processing | confirmed | unlocked
  const [plan, setPlan] = useState('annual') // 'monthly' | 'annual'
  const buy = async () => {
    setStage('processing')
    // Mock payment — no real charge. Simulate a processing delay, then confirm.
    await new Promise(r => setTimeout(r, 2200))
    try {
      await f(API + '/api/plus/purchase', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }, body: JSON.stringify({ plan }) })
    } catch {}
    setStage('confirmed')
    await new Promise(r => setTimeout(r, 1100))
    setStage('unlocked')
  }

  if (stage === 'unlocked') {
    return <div className="plus-unlock" onClick={() => { onUnlocked(); onClose() }}>
      <div className="plus-burst"></div>
      <div className="plus-unlock-inner">
        <div className="plus-check">✓</div>
        <div className="plus-crown">PAULA <span>PLUS</span></div>
        <h1>You're unlocked.</h1>
        <p>Unlimited messages, new chats, and full access — all yours.</p>
        <button className="plus-done" onClick={() => { onUnlocked(); onClose() }}>Let's go →</button>
      </div>
      {[...Array(60)].map((_, i) => {
        const left = Math.random() * 100
        const delay = Math.random() * 0.6
        const dur = 2.4 + Math.random() * 1.6
        const size = 6 + Math.random() * 8
        const drift = (Math.random() - 0.5) * 240
        const colors = ['#10b981', '#34d399', '#6ee7b7', '#f5a623', '#ffffff', '#a7f3d0']
        return <span key={i} className="plus-confetti" style={{
          left: left + '%', top: '-24px',
          width: size + 'px', height: (size * (0.6 + Math.random())) + 'px',
          background: colors[i % colors.length],
          borderRadius: i % 3 === 0 ? '50%' : '2px',
          animationDelay: delay + 's',
          animationDuration: dur + 's',
          '--drift': drift + 'px',
        }} />
      })}
    </div>
  }

  return <div className="cl-overlay" onClick={stage === 'offer' ? onClose : undefined}>
    <div className="plus-modal" onClick={e => e.stopPropagation()}>
      {stage === 'offer' && <>
        <div className="plus-badge">PAULA <span>PLUS</span></div>

        <div className="plus-plans">
          <button className={"plus-plan"+(plan==='monthly'?" plus-plan-on":"")} onClick={()=>setPlan('monthly')}>
            <span className="plus-plan-name">Monthly</span>
            <span className="plus-plan-price">$9.99<span>/mo</span></span>
          </button>
          <button className={"plus-plan"+(plan==='annual'?" plus-plan-on":"")} onClick={()=>setPlan('annual')}>
            <span className="plus-plan-badge">2 months free</span>
            <span className="plus-plan-name">Annual</span>
            <span className="plus-plan-price">$99<span>/yr</span></span>
          </button>
        </div>

        <ul className="plus-feats">
          <li><span className="plus-dot"/>Unlimited messages — no daily cap</li>
          <li><span className="plus-dot"/>Create unlimited chats</li>
          <li><span className="plus-dot"/>Full Analyze access &amp; deep dives</li>
          <li><span className="plus-dot"/>Everything Paula can do, unlocked</li>
        </ul>
        <button className="plus-buy" onClick={buy}>{plan==='annual'?'Get Plus — $99/year':'Get Plus — $9.99/month'}</button>
        <button className="plus-cancel" onClick={onClose}>Maybe later</button>
        <div className="plus-fine">Demo checkout — no real payment is processed.</div>
      </>}
      {stage === 'processing' && <div className="plus-proc">
        <div className="plus-spinner"></div>
        <h2>Processing payment…</h2>
        <p>Securing your subscription</p>
      </div>}
      {stage === 'confirmed' && <div className="plus-proc">
        <div className="plus-check-sm">✓</div>
        <h2>Payment confirmed</h2>
        <p>Unlocking Paula Plus…</p>
      </div>}
    </div>
  </div>
}

function MainApp({ user, token, logout, setUser, theme, setTheme }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [quickTicker, setQuickTicker] = useState('')
  const [quickResult, setQuickResult] = useState(null)
  const [quickLoading, setQuickLoading] = useState(false)
  const [chatSearch, setChatSearch] = useState('')
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef(null)
  const [showPlus, setShowPlus] = useState(false)
  // Plus access: Plus subscribers, the admin, and authorized accounts are unlocked.
  const isPlus = !!(user.plus || user.is_admin)

  const toggleVoice = () => {
    if (listening) {
      recognitionRef.current?.stop()
      recognitionRef.current = null
      setListening(false)
      return
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const recognition = new SR()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'en-US'
    recognitionRef.current = recognition
    recognition.onresult = (e) => {
      const transcript = Array.from(e.results).map(r => r[0].transcript).join('')
      setInput(transcript)
    }
    recognition.onend = () => {
      // Restart if still supposed to be listening (browser auto-stops after silence)
      if (recognitionRef.current) {
        try { recognitionRef.current.start() } catch {}
      }
    }
    recognition.onerror = (e) => {
      if (e.error === 'no-speech') return // ignore silence, keep listening
      setListening(false)
      recognitionRef.current = null
    }
    recognition.start()
    setListening(true)
  }
  const [sending, setSending] = useState(false)
  const [loadingText, setLoadingText] = useState('')
  const sendingChatRef = useRef(null) // which chat the current send is for
  const cancelledRef = useRef(false)  // set true to abort an in-flight response
  const abortRef = useRef(null)       // AbortController for the fetch
  const [account, setAccount] = useState(null)
  const [positions, setPositions] = useState([])
  const [autopilot, setAutopilot] = useState(false)
  const apChatRef = useRef(null) // tracks which chat ID autopilot logs go to
  const userIdRef = useRef(user.id) // current account id, for account-scoped sound gating
  const apToggleAtRef = useRef(0) // timestamp of last manual toggle — guards against poll races
  const [connected, setConnected] = useState(false)
  const [spyTrend, setSpyTrend] = useState(null)
  const [selectedPos, setSelectedPos] = useState(null)
  const [toasts, setToasts] = useState([])
  const [view, setView] = useState('chat')
  const [perf, setPerf] = useState(null)
  const [showChangelog, setShowChangelog] = useState(() => {
    const seen = localStorage.getItem('paula-changelog-seen')
    if (seen !== VERSION) return true
    return false
  })
  const dismissChangelog = () => { setShowChangelog(false); localStorage.setItem('paula-changelog-seen', VERSION) }
  
  const [sideOpen, setSideOpen] = useState(window.innerWidth > 760)
  const [pinnedChats, setPinnedChats] = useState(() => {
    try { return JSON.parse(localStorage.getItem('paula-pinned') || '[]') } catch { return [] }
  })
  const togglePin = (id) => {
    const next = pinnedChats.includes(id) ? pinnedChats.filter(x => x !== id) : [...pinnedChats, id]
    setPinnedChats(next)
    localStorage.setItem('paula-pinned', JSON.stringify(next))
  }

  // ── Chat system ──
  const chatKey = 'paula-chats-' + user.id
  const chatsRef = useRef(JSON.parse(localStorage.getItem(chatKey) || '[]'))
  const [chats, _setChats] = useState(chatsRef.current)
  const chatIdRef = useRef(localStorage.getItem('paula-chat-id-' + user.id) || null)
  const [chatId, _setChatId] = useState(chatIdRef.current)

  const persist = (updated) => {
    chatsRef.current = updated
    _setChats(updated)
    localStorage.setItem(chatKey, JSON.stringify(updated))
  }

  // New account / no chats yet → open a fresh blank chat (welcome screen) by
  // default so the user lands in a ready-to-type conversation, not an empty void.
  useEffect(() => {
    if (chatsRef.current.length === 0) {
      const id = Date.now().toString() + "-" + Math.random().toString(36).slice(2, 8)
      const fresh = [{ id, title: 'New chat', messages: [], created: new Date().toISOString() }]
      persist(fresh)
      chatIdRef.current = id; _setChatId(id)
      localStorage.setItem('paula-chat-id-' + user.id, id)
      setMessages([])
    }
  }, [])

  const setActiveChatId = (id) => {
    chatIdRef.current = id
    _setChatId(id)
    localStorage.setItem('paula-chat-id-' + user.id, id || '')
  }

  // Save current messages into the active chat
  const saveCurrentChat = () => {
    const id = chatIdRef.current
    if (id && messages.length > 0) {
      persist(chatsRef.current.map(c => c.id === id ? { ...c, messages, updated: new Date().toISOString() } : c))
    }
  }

  const toggleAutopilot = async () => {
    const wasOn = autopilot
    apToggleAtRef.current = Date.now()
    setAutopilot(!wasOn)
    if (wasOn) {
      const apId = apChatRef.current
      if (apId && chatIdRef.current !== apId) switchChat(apId)
      setMessages(prev => [...prev, { role: 'assistant', content: '🔴 **Autopilot stopped.**', type: 'autopilot' }])
      if (apId) persist(chatsRef.current.map(c => c.id === apId ? { ...c, title: 'Autopilot Off' } : c))
      apChatRef.current = null
    } else {
      newChat()
      const apId = chatIdRef.current
      apChatRef.current = apId
      persist(chatsRef.current.map(c => c.id === apId ? { ...c, title: 'Autopilot Session' } : c))
      setMessages([{ role: 'assistant', content: '🟢 **Autopilot started.** Scanning every 5 minutes.\n\nLogs will appear here.', type: 'autopilot' }])
    }
    setView('chat')
    try {
      const r = await f(API+'/api/autopilot/'+(wasOn?'stop':'start'),{method:'POST'}).then(r=>r.json())
      if (!r.ok) {
        apToggleAtRef.current = 0; setAutopilot(wasOn); if (!wasOn) apChatRef.current = null
        const msg = r.error || 'Autopilot could not start'
        addToast(msg.includes('signed in') || msg.includes('restricted') ? 'Sign out and back in — your session expired' : msg, 'sell')
      }
    } catch { apToggleAtRef.current = 0; setAutopilot(wasOn); if (!wasOn) apChatRef.current = null; addToast("Can't reach backend", 'sell') }
  }

  const newChat = () => {
    // Free tier: only one chat. Creating new chats is a Plus feature.
    if (!isPlus && chatsRef.current.length >= 1) { setShowPlus(true); return }
    saveCurrentChat()
    const id = Date.now().toString() + "-" + Math.random().toString(36).slice(2, 8)
    persist([{ id, title: 'New chat', messages: [], created: new Date().toISOString() }, ...chatsRef.current])
    setActiveChatId(id)
    setMessages([])
    setView('chat')
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
      localStorage.setItem(chatKey, JSON.stringify(updated))
    }, 500)
  }, [messages])
  const [settings, setSettings] = useState(() => {
    try { return JSON.parse(localStorage.getItem('paula-settings-' + user.id)) || {} } catch { return {} }
  })
  const settingsRef = useRef(settings)
  useEffect(() => {
    settingsRef.current = settings
    if (settings.fontSize) document.documentElement.style.setProperty('--chat-fs', settings.fontSize)
  }, [settings])
  const updateSetting = (k, v) => { const n = { ...settings, [k]: v }; setSettings(n); localStorage.setItem('paula-settings-' + user.id, JSON.stringify(n)) }
  const snd = (fn) => { if (settingsRef.current.sounds !== false) fn() }

  const messagesEnd = useRef(null)
  const chatScrollRef = useRef(null)
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
          if (event === 'connected') { if (Date.now() - apToggleAtRef.current > 10000) setAutopilot(data.autopilot) }
          if (event === 'autopilot') {
            if (data.status === 'started') { setAutopilot(true) }
            if (data.status === 'stopped') { setAutopilot(false); apChatRef.current = null }

            // Build the message
            let apMsg = null
            if (data.status === 'scanned' && data.log && data.log.length > 0) {
              // Only the ACCOUNT that owns autopilot should hear it — match the
              // owner id the backend tags on the event (works across all of that
              // account's devices/sessions, silent for everyone else).
              if (data.ap_owner_id != null && data.ap_owner_id === userIdRef.current && settingsRef.current.scanSound !== false) playNotify()
              const summary = data.log.slice(0, 8).join('\n')
              const extra = data.buys || data.sells || data.shorts
                ? `\n\n**Trades:** ${data.buys||0} bought, ${data.sells||0} sold, ${data.shorts||0} shorted`
                : ''
              const scanTime = data.log[0]?.match(/\d+:\d+ [AP]M/)?.[0] || ''
              apMsg = { role: 'assistant', content: `📡 **Scan Complete** — ${data.scanned||'?'} stocks scanned\n\n${summary}${extra}`, type: 'autopilot', scanTime }
            }
            if (data.status === 'paused' && data.reason) {
              apMsg = { role: 'assistant', content: `⏸ **Autopilot paused** — ${data.reason}`, type: 'autopilot' }
            }

            // Route to the autopilot chat
            if (apMsg && apChatRef.current) {
              if (chatIdRef.current === apChatRef.current) {
                // User is viewing the autopilot chat — add directly (dedup by scanTime)
                if (apMsg.content.includes('paused')) {
                  setMessages(prev => {
                    const lastAP = [...prev].reverse().find(m => m.type === 'autopilot')
                    if (lastAP && lastAP.content.includes('paused')) return prev
                    return [...prev, apMsg]
                  })
                } else {
                  setMessages(prev => {
                    // Don't add if last scan message has same time
                    const lastScan = [...prev].reverse().find(m => m.type === 'autopilot' && m.content?.includes('Scan Complete'))
                    if (lastScan && apMsg.scanTime && lastScan.scanTime === apMsg.scanTime) return prev
                    return [...prev, apMsg]
                  })
                }
              } else {
                // User is in a different chat — save to autopilot chat in localStorage
                const apId = apChatRef.current
                const updated = chatsRef.current.map(c => {
                  if (c.id !== apId) return c
                  const msgs = c.messages || []
                  if (apMsg.content.includes('paused') && msgs.some(m => m.content?.includes('paused'))) return c
                  return { ...c, messages: [...msgs, apMsg] }
                })
                persist(updated)
              }
            }
          }
          if (event === 'trade') {
            const act = data.action, ticker = data.ticker || data.symbol || ''
            // Broadcast trades fan out to ALL clients on the shared backend. Only
            // the autopilot-owning ACCOUNT hears autopilot/EOD trade sounds (matched
            // by the owner id the backend tags). Manual trades you make play their
            // own sound locally. Toasts still show for everyone (shared account).
            const owns = data.ap_owner_id != null && data.ap_owner_id === userIdRef.current
            if (act === 'buy') { if (owns) snd(playBuy); addToast('Bought ' + ticker, 'buy') }
            else if (act === 'sell') { if (owns) snd(playSell); addToast('Sold ' + ticker, 'sell') }
            else if (act === 'short') { if (owns) snd(playSell); addToast('Shorted ' + ticker, 'sell') }
            else if (act === 'cover') { if (owns) snd(playProfit); addToast('Covered ' + ticker, 'buy') }
            else if (act === 'close_all') { if (owns) snd(playAlert); addToast('All positions closed', 'warn') }
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
      if (s.ok) setSpyTrend(s.data)
      // Don't let a poll override the toggle within 10s of a manual change —
      // the server task may not have settled yet, which caused the "turns off
      // right after turning on" flicker.
      if (Date.now() - apToggleAtRef.current > 10000) setAutopilot(h.autopilot)
    } catch {}
  }, [])

  useEffect(() => {
    // Load current chat messages on mount
    if (chatId) {
      const chat = chatsRef.current.find(c => c.id === chatId)
      if (chat?.messages) setMessages(chat.messages)
    }
    refreshData()
    // Poll account/positions every 5s — but skip refreshes while the tab is
    // hidden (background), and fire one immediately when the user returns. Saves
    // battery, bandwidth, and backend load when Paula isn't on screen.
    const i = setInterval(() => { if (!document.hidden) refreshData() }, 5000)
    const onVis = () => { if (!document.hidden) refreshData() }
    document.addEventListener('visibilitychange', onVis)
    return () => { clearInterval(i); document.removeEventListener('visibilitychange', onVis) }
  }, [refreshData])
  useEffect(() => {
    // Smart auto-scroll: only pull to the bottom if the user is ALREADY near the
    // bottom. If they've scrolled up to read while a reply streams, leave them be
    // (no more fighting the scroll / yanking them back down).
    const el = chatScrollRef.current
    if (!el) { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }); return }
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    if (nearBottom) messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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
    const id = Date.now().toString() + "-" + Math.random().toString(36).slice(2, 8)
    persist([{ id, title: 'New chat', messages: [], created: new Date().toISOString() }, ...chatsRef.current])
    setActiveChatId(id)
    setMessages([])
    f(API + '/api/chat/clear', { method: 'POST' }).catch(() => {})
    return id
  }

  const sendMessage = async (msg) => {
    if (!msg || (sending && sendingChatRef.current === chatIdRef.current)) return
    setSending(true)
    cancelledRef.current = false
    abortRef.current = new AbortController()
    setInput('')
    setView('chat')
    // Thinking sequence — contextual, cycles while waiting so it feels alive.
    const ml = msg.toLowerCase()
    const tkm = msg.match(/[A-Z]{1,5}/)
    let _seq
    if (/^analyze |^check |tell me about/i.test(ml)) {
      const t = tkm ? tkm[0] : 'the stock'
      _seq = [`Pulling ${t} data...`, `Reading the chart...`, `Checking the signal...`, `Weighing the setup...`]
    } else if (/market|regime|spy/i.test(ml)) {
      _seq = ['Checking the market...', 'Reading SPY trend...', 'Gauging risk...']
    } else if (/buy|sell|short|cover/i.test(ml)) {
      _seq = ['Sizing the trade...', 'Placing the order...']
    } else if (/gain|mover|top|scan|setup|pick|swing|idea/i.test(ml)) {
      _seq = ['Scanning the market...', 'Running the signal engine...', 'Ranking setups...', 'Picking the best ones...']
    } else if (/news|latest|happening|why is|why did/i.test(ml)) {
      _seq = ['Searching for news...', 'Reading the headlines...', 'Pulling it together...']
    } else if (/recap|today|performance/i.test(ml)) {
      _seq = ['Loading your recap...', 'Tallying the day...']
    } else {
      _seq = ['Thinking...', 'Working it out...', 'Almost there...']
    }
    setLoadingText(_seq[0])
    let _si = 0
    const _thinkTimer = setInterval(() => {
      _si = (_si + 1) % _seq.length
      setLoadingText(_seq[_si])
    }, 1400)
    // store so we can clear it when done
    abortRef.current._thinkTimer = _thinkTimer

    // Always ensure chat exists
    const targetId = ensureChat()
    sendingChatRef.current = targetId
    const isFirstMsg = messages.length === 0

    // Snapshot this chat's prior turns for backend context (each chat independent)
    const _histSnapshot = messages.filter(m => m.role === 'user' || m.role === 'assistant').slice(-12).map(m => ({ role: m.role, content: m.content }))

    // Show user message immediately
    setMessages(prev => [...prev, { role: 'user', content: msg, time: new Date().toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'}) }])

    try {
      const res = await f(API + '/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
        signal: abortRef.current.signal,
        body: JSON.stringify({
          message: msg,
          // Send this chat's recent turns so the backend treats each chat
          // independently (no cross-chat context bleed).
          history: _histSnapshot
        })
      })
      const data = await res.json()
      try { clearInterval(abortRef.current?._thinkTimer) } catch {}

      // Free-tier daily limit hit on a PRIOR message — backend blocked this one
      // outright. Surface the Plus upsell instead of a reply.
      if (data.limit_reached) {
        setSending(false)
        setShowPlus(true)
        return
      }

      if (data.ok) {
        const text = data.message || ''
        const assistantMsg = {
          role: 'assistant', content: text, streaming: false,
          type: data.type, ticker: data.ticker || null,
          tickers: data.tickers || [], signal: data.trade_signal || null,
          signalData: data.signal_data || null,
          showChart: ['analysis','price','stock_ideas'].includes(data.type),
          time: new Date().toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'})
        }

        // Check if user is still in the same chat
        if (chatIdRef.current === targetId) {
          // Still here — animate typing
          const words = text.split(/(\s+)/)
          setMessages(prev => [...prev, { ...assistantMsg, content: '', streaming: true }])

          let shown = ''
          for (let i = 0; i < words.length; i++) {
            // Cancelled mid-response: keep what's shown so far, mark it stopped.
            if (cancelledRef.current && chatIdRef.current === targetId) {
              setMessages(prev => {
                const m = [...prev]; const last = m[m.length - 1]
                if (last?.streaming) m[m.length - 1] = { ...last, streaming: false, content: (shown || '') + ' ⏹' }
                return m
              })
              break
            }
            // User switched away: save the full response to the original chat.
            if (chatIdRef.current !== targetId) {
              const updated = chatsRef.current.map(c => {
                if (c.id !== targetId) return c
                const msgs = c.messages || []
                const fixed = msgs.map(m => m.streaming ? { ...assistantMsg } : m)
                if (!msgs.some(m => m.streaming)) fixed.push(assistantMsg)
                return { ...c, messages: fixed }
              })
              persist(updated)
              break
            }
            shown += words[i]
            const snap = shown
            setMessages(prev => {
              const m = [...prev]; const last = m[m.length - 1]
              if (last?.streaming) m[m.length - 1] = { ...last, content: snap }
              return m
            })
            if (i % 3 === 0) await new Promise(r => setTimeout(r, 15))
          }

          // Finalize if still in same chat AND not cancelled
          if (chatIdRef.current === targetId && !cancelledRef.current) {
            setMessages(prev => {
              const m = [...prev]; const last = m[m.length - 1]
              if (last) m[m.length - 1] = { ...last, streaming: false, content: text }
              // Immediately persist this chat's full message list into chatsRef so
              // switching away can't lose or cross-contaminate it.
              persist(chatsRef.current.map(c => c.id === targetId ? { ...c, messages: m, updated: new Date().toISOString() } : c))
              return m
            })
          }
        } else {
          // User already switched — save directly to original chat
          const updated = chatsRef.current.map(c => {
            if (c.id !== targetId) return c
            return { ...c, messages: [...(c.messages || []), assistantMsg] }
          })
          persist(updated)
        }

        // Sounds
        if (data.type === 'trade' && data.message) {
          if (data.message.includes('Bought')) { snd(playBuy); addToast(data.message.slice(0, 60), 'buy') }
          else if (data.message.includes('Sold') || data.message.includes('Shorted')) { snd(playSell); addToast(data.message.slice(0, 60), 'sell') }
          else if (data.message.includes('Covered')) { snd(playProfit); addToast(data.message.slice(0, 60), 'buy') }
        } else { snd(playTick) }

        if (data.autopilot !== undefined && Date.now() - apToggleAtRef.current > 10000) setAutopilot(data.autopilot)
      } else {
        if (chatIdRef.current === targetId) {
          setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ ' + (data.error || 'Something went wrong') }])
        } else {
          // Save error to original chat
          persist(chatsRef.current.map(c => c.id === targetId ? { ...c, messages: [...(c.messages||[]), { role: 'assistant', content: '⚠️ ' + (data.error || 'Something went wrong') }] } : c))
        }
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
    } catch (err) {
      // If the user cancelled, don't show a "connection lost" error.
      if (!(cancelledRef.current || (err && err.name === 'AbortError'))) {
        setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Connection lost.' }])
      }
    }

    try { clearInterval(abortRef.current?._thinkTimer) } catch {}
    setSending(false)
    setLoadingText('')
    sendingChatRef.current = null
    cancelledRef.current = false
    abortRef.current = null
    inputRef.current?.focus()
  }

  // Cancel Paula mid-response
  const cancelSend = () => {
    cancelledRef.current = true
    try { clearInterval(abortRef.current?._thinkTimer) } catch {}
    try { abortRef.current?.abort() } catch {}
    setSending(false)
    setLoadingText('')
  }

  const send = () => {
    const msg = input.trim()
    if (!msg) return
    // Stop mic on send
    if (listening) {
      recognitionRef.current?.stop()
      recognitionRef.current = null
      setListening(false)
    }
    sendMessage(msg)
  }

  const quickLookup = async (ticker) => {
    if (!ticker || ticker.length > 5) return
    setQuickLoading(true)
    try {
      const r = await f(API + '/api/quick/' + ticker.toUpperCase()).then(r => r.json())
      if (r.ok) setQuickResult(r)
      else setQuickResult(null)
    } catch { setQuickResult(null) }
    setQuickLoading(false)
  }
  const loadDashboard = async () => { try { const r = await f(API+'/api/performance?_t='+Date.now()).then(r=>r.json()); if(r.ok)setPerf(r) } catch{} }

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
          <div className="cl-top">
            <div className="cl-top-l">
              <span className="logo-p cl-logo">P</span>
              <div>
                <span className="cl-ver-title">Paula v{VERSION}</span>
                <span className="cl-date">{VERSION_DATE}</span>
              </div>
            </div>
            <button className="cl-close" onClick={dismissChangelog}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>

          <div className="cl-hero">
            <h2>What's new</h2>
            <p>Every update to Paula, newest first.</p>
          </div>

          <div className="cl-body cl-history">
            {CHANGELOG_DATA.map((rel, i) => (
              <ChangelogRelease key={rel.v} rel={rel} defaultOpen={i === 0} latest={i === 0} />
            ))}
          </div>

          <div className="cl-footer">
            <button className="cl-dismiss" onClick={dismissChangelog}>Continue to Paula</button>
          </div>
        </div>
      </div>}

      {/* Backdrop behind the mobile slide-in rail — tap to close */}
      <div className={'rail-backdrop'+(sideOpen?' rail-backdrop-on':'')} onClick={()=>setSideOpen(false)} />

      {/* Hover-expand rail (desktop) / slide-in drawer (mobile) */}
      <aside className={'rail'+((sideOpen&&window.innerWidth<=760)?' rail-pinned rail-mobile-open':'')}>
        <div className="rl-logo"><span className="logo-p rl-mark">P</span><b className="rl-name">Paula</b></div>

        <button className={"rl-item rl-new"+(!isPlus && chats.length>=1?' rl-locked':'')} onClick={newChat} title={!isPlus && chats.length>=1?"New chat (Paula Plus)":"New chat"}>
          <i className="rl-ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg></i><span>New chat{!isPlus && chats.length>=1&&<svg className="rl-lock" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>}</span>
        </button>

        {[
          ['chat','Chat',<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>],
          ['analyze','Analyze',<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>],
          ['stats','Portfolio',<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><rect x="7" y="11" width="3" height="6"/><rect x="13" y="7" width="3" height="10"/></svg>],
        ].map(([v,label,icon])=>{
          const locked = !isPlus && (v==='analyze'||v==='stats')
          return (
          <button key={v} className={'rl-item'+(view===v?' rl-on':'')+(locked?' rl-locked':'')} onClick={()=>{ if(locked){setShowPlus(true);return} setView(v);if(v==='stats')loadDashboard();if(window.innerWidth<=760)setSideOpen(false)}} title={locked?label+' (Paula Plus)':label}>
            <i className="rl-ic">{icon}</i><span>{label}{locked&&<svg className="rl-lock" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>}</span>
          </button>
        )})}

        <div className="rl-scroll">
          <div className="rl-sec">Chats</div>
          {(()=>{
            const q = chatSearch.toLowerCase()
            const filtered = chats.filter(c => !q || c.title?.toLowerCase().includes(q))
            const sorted = [...filtered].sort((a,b) => {
              const ta = new Date(a.updated || a.created || 0).getTime()
              const tb = new Date(b.updated || b.created || 0).getTime()
              return tb - ta
            })
            return sorted.slice(0, 25).map(c => (
              <div key={c.id} className={'rl-chat' + (chatId === c.id ? ' rl-chat-on' : '')} onClick={() => {switchChat(c.id);setView('chat')}}>
                <span className="rl-chat-title">{c.title}</span>
                <button className="rl-chat-x" onClick={(e) => { e.stopPropagation(); deleteChat(c.id) }} aria-label="Delete chat">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
                </button>
              </div>
            ))
          })()}
          {positions.length>0&&<>
            <div className="rl-sec">Positions <span className={'rl-sec-tot '+(totalUnrealized>=0?'up':'dn')}>{totalUnrealized>=0?'+':''}${Math.abs(totalUnrealized).toFixed(0)}</span></div>
            {positions.map((p,i)=>(
              <div key={i} className="rl-pos" onClick={()=>{setSelectedPos(selectedPos===p.ticker?null:p.ticker);setView('chat')}}>
                <span className="rl-pos-sym">{p.ticker}</span>
                <span className={'rl-pos-pnl '+(p.unrealized_pnl>=0?'up':'dn')}>{p.unrealized_pnl>=0?'+':'−'}${Math.abs(p.unrealized_pnl).toFixed(0)}</span>
              </div>
            ))}
          </>}

          {['parjan.d@icloud.com','pinakin.d@moftmail.com'].includes((user?.email||'').toLowerCase()) && <>
          <div className="rl-sec">Automation</div>
          <button className={'rl-item rl-ap'+(autopilot?' rl-ap-on':'')} onClick={()=>toggleAutopilot()} title="Autopilot">
            <i className="rl-ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/></svg></i><span>Autopilot<small className={autopilot?'c-on':''}>{autopilot?'on':'off'}</small></span>
          </button>
          </>}
        </div>

        <div className="rl-foot">
          <button className={'rl-item'+(view==='settings'?' rl-on':'')} onClick={()=>setView('settings')} title="Settings">
            <i className="rl-ic"><svg width="19" height="19" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><path d="M10.33 2.32a1 1 0 0 1 .97-.82h1.4a1 1 0 0 1 .97.82l.2 1.1a1 1 0 0 0 .66.76 7.6 7.6 0 0 1 .9.37 1 1 0 0 0 1-.08l.92-.65a1 1 0 0 1 1.28.11l.99.99a1 1 0 0 1 .11 1.28l-.65.92a1 1 0 0 0-.08 1c.14.29.27.59.37.9a1 1 0 0 0 .76.66l1.1.2a1 1 0 0 1 .82.97v1.4a1 1 0 0 1-.82.97l-1.1.2a1 1 0 0 0-.76.66c-.1.31-.23.61-.37.9a1 1 0 0 0 .08 1l.65.92a1 1 0 0 1-.11 1.28l-.99.99a1 1 0 0 1-1.28.11l-.92-.65a1 1 0 0 0-1-.08c-.29.14-.59.27-.9.37a1 1 0 0 0-.66.76l-.2 1.1a1 1 0 0 1-.97.82h-1.4a1 1 0 0 1-.97-.82l-.2-1.1a1 1 0 0 0-.66-.76 7.6 7.6 0 0 1-.9-.37 1 1 0 0 0-1 .08l-.92.65a1 1 0 0 1-1.28-.11l-.99-.99a1 1 0 0 1-.11-1.28l.65-.92a1 1 0 0 0 .08-1 7.6 7.6 0 0 1-.37-.9 1 1 0 0 0-.76-.66l-1.1-.2a1 1 0 0 1-.82-.97v-1.4a1 1 0 0 1 .82-.97l1.1-.2a1 1 0 0 0 .76-.66c.1-.31.23-.61.37-.9a1 1 0 0 0-.08-1l-.65-.92a1 1 0 0 1 .11-1.28l.99-.99a1 1 0 0 1 1.28-.11l.92.65a1 1 0 0 0 1 .08c.29-.14.59-.27.9-.37a1 1 0 0 0 .66-.76z"/><circle cx="12" cy="12" r="3" fill="var(--c0,#0b0b10)" stroke="currentColor" strokeWidth="1.5"/></svg></i><span>Settings</span>
          </button>
          <button className="rl-item rl-profile" onClick={()=>setView('settings')} title={settings.userName||user?.username||'Account'}>
            <i className="rl-ic"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg></i><span>{settings.userName||user?.username||'PJ'}</span>
          </button>
          <button className="rl-item rl-signout" onClick={logout} title="Sign out">
            <i className="rl-ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg></i><span>Sign out</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="main">
        {/* Slim top bar — hamburger (mobile) + equity ticker; nav lives in the rail */}
        <div className="hdr hdr-slim">
          <button className="ham" onClick={()=>setSideOpen(true)} aria-label="Open menu">☰</button>
          <button className="hdr-changelog" onClick={()=>setShowChangelog(true)} title="What's new">v{VERSION}</button>
          <div className="hdr-ticker">
            {account&&<>
              <span className="hdr-eq">${account.equity.toLocaleString(undefined,{maximumFractionDigits:0})}</span>
              <span className={'hdr-eq '+(pnl>=0?'up':'dn')}>{pnl>=0?'+':''}${Math.abs(pnl).toFixed(0)}</span>
            </>}
          </div>
        </div>

        {view==='analyze'?<AnalyzeView sendMessage={sendMessage} setView={setView}/>

        :view==='stats'?<DashView perf={perf}/>

        :view==='plus'?<PlusPage isPlus={isPlus} onBuy={()=>setShowPlus(true)} setView={setView}/>

        :view==='settings'?<SetView settings={settings} update={updateSetting} user={user} token={token} logout={logout} autopilot={autopilot} setAutopilot={setAutopilot} persist={persist} setActiveChatId={setActiveChatId} setMessages={setMessages} setShowChangelog={setShowChangelog} setUser={setUser} theme={theme} setTheme={setTheme} setView={setView}/>
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
              <div className="db-chart"><Suspense fallback={<ChartFallback/>}><Chart ticker={p.ticker} signal={null} height={200}/></Suspense></div>
            </div>)})()}
          <div className="chat" ref={chatScrollRef}>
            <div className="chat-inner">
            {messages.length===0&&!(sending && sendingChatRef.current === chatIdRef.current)&&(
              <div className="welcome">
                <span className="logo-p w-mark">P</span>
                <h1 className="w-greet"><span className="w-hi">{(() => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' })()}, {name}.</span></h1>
                <p className="w-q"><Typewriter/></p>

                {account&&<div className="w-snap">
                  <div className="ws-cell"><span className="ws-l">Equity</span><span className="ws-v">${account.equity.toLocaleString(undefined,{maximumFractionDigits:0})}</span></div>
                  <div className="ws-cell"><span className="ws-l">Open P/L</span><span className={'ws-v '+(pnl>=0?'up':'dn')}>{pnl>=0?'+':'−'}${Math.abs(pnl).toFixed(0)}</span></div>
                  {spyTrend&&<div className="ws-cell"><span className="ws-l">Market</span><span className={'ws-v '+(spyTrend.change_pct>=0?'up':'dn')}>SPY {spyTrend.change_pct>=0?'+':''}{spyTrend.change_pct}%</span></div>}
                  <div className="ws-cell"><span className="ws-l">Positions</span><span className="ws-v">{positions.length}</span></div>
                </div>}

                <div className="w-pills">
                  {[
                    {q:'Find swing setups', cmd:'Find me the 5 best swing trade setups right now'},
                    {q:'Check the market', cmd:'How is the market looking today for swing trading?'},
                  ].map((p,i)=>(
                    <button key={i} className="w-pill" disabled={sending && sendingChatRef.current === chatIdRef.current} onClick={()=>sendMessage(p.cmd)}>{p.q}</button>
                  ))}
                  <button className="w-pill" onClick={()=>setView('analyze')}>Analyze a stock</button>
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
                      {m.showChart && m.tickers?.length>1?(
                        <ChartTabs tickers={m.tickers} signal={m.signal}/>
                      ):m.showChart && (m.ticker||m.tickers?.[0])?(
                        <div className="ai-chart"><Suspense fallback={<ChartFallback/>}><Chart ticker={m.ticker||m.tickers[0]} signal={m.signal} height={260}/></Suspense></div>
                      ):null}
                      {m.signalData && <SignalCard data={m.signalData} onExecute={(ticker, side) => sendMessage((side === 'EXIT' ? 'Sell ' : 'Buy ') + ticker)}/>}
                      {m.time&&!m.streaming&&<div className="msg-time">{m.time}</div>}
                    </div>
                  </div>
                ):(<><div className="user-bubble">{m.content.split(/(@[A-Z]{1,5})/g).map((part,i) => part.match(/^@[A-Z]{1,5}$/) ? <span key={i} className="mention">{part}</span> : part)}</div>{m.time&&<div className="msg-time">{m.time}</div>}</>)}
              </div>))}
            {sending&&sendingChatRef.current===chatIdRef.current&&!messages.some(m=>m.streaming)&&<div className="msg msg-assistant"><div className="ai"><div className="ai-av">P</div><div className="ai-body"><div className="ai-name">Paula</div><div className="loading-state"><div className="dots"><span/><span/><span/></div><span className="loading-txt">{loadingText}</span></div></div></div></div>}
            <div ref={messagesEnd}/>
            </div>
          </div>
          <div className={'input-area'+(messages.length?' ia-active':'')}><div className="input-wrap"><div className="input-box">
            <textarea ref={inputRef} value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();if(!(sending && sendingChatRef.current === chatIdRef.current))send()}}} placeholder="Message Paula — ask for a setup, scan, or recap..." rows={1} className="chat-textarea"/>
            <button className={'mic'+(listening?' mic-on':'')} onClick={toggleVoice} title="Voice input">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0014 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
            </button>
            {sending && sendingChatRef.current === chatIdRef.current
              ? <button className="send send-stop" onClick={cancelSend} title="Stop generating"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="3"/></svg></button>
              : <button className="send" onClick={send}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9Z"/></svg></button>
            }
          </div>
          {autopilot&&<div className="input-hints">
            <span className="ih-left"><span className="ih-dot"/>AUTOPILOT ACTIVE</span>
          </div>}
          </div></div>
        </>)}
      </main>
      {showPlus && <PlusModal token={token} onClose={() => setShowPlus(false)} onUnlocked={() => setUser && setUser(u => ({ ...u, plus: true }))}/>}
    </div>)
}

const PHRASES = ["what are we trading today?","what's the play today?","let's find some setups.","what are we watching?","let's get to work.","what's on your radar?","ready to make some moves?"]
const TICKER_DB = [
  // ── Mega Cap ──
  {t:'AAPL',n:'Apple'},{t:'MSFT',n:'Microsoft'},{t:'NVDA',n:'Nvidia'},{t:'GOOGL',n:'Alphabet'},{t:'AMZN',n:'Amazon'},
  {t:'META',n:'Meta'},{t:'TSLA',n:'Tesla'},{t:'BRK.B',n:'Berkshire Hathaway'},{t:'TSM',n:'Taiwan Semi'},
  // ── Tech ──
  {t:'AMD',n:'AMD'},{t:'NFLX',n:'Netflix'},{t:'CRM',n:'Salesforce'},{t:'AVGO',n:'Broadcom'},{t:'ORCL',n:'Oracle'},
  {t:'ADBE',n:'Adobe'},{t:'INTC',n:'Intel'},{t:'CSCO',n:'Cisco'},{t:'IBM',n:'IBM'},{t:'QCOM',n:'Qualcomm'},
  {t:'TXN',n:'Texas Instruments'},{t:'MU',n:'Micron'},{t:'AMAT',n:'Applied Materials'},{t:'LRCX',n:'Lam Research'},
  {t:'KLAC',n:'KLA Corp'},{t:'SNPS',n:'Synopsys'},{t:'CDNS',n:'Cadence'},{t:'MRVL',n:'Marvell'},
  {t:'PANW',n:'Palo Alto Networks'},{t:'CRWD',n:'CrowdStrike'},{t:'ZS',n:'Zscaler'},{t:'FTNT',n:'Fortinet'},
  {t:'NET',n:'Cloudflare'},{t:'DDOG',n:'Datadog'},{t:'SNOW',n:'Snowflake'},{t:'MDB',n:'MongoDB'},
  {t:'NOW',n:'ServiceNow'},{t:'INTU',n:'Intuit'},{t:'WDAY',n:'Workday'},{t:'HUBS',n:'HubSpot'},
  {t:'TTD',n:'Trade Desk'},{t:'ANET',n:'Arista Networks'},{t:'SMCI',n:'Super Micro'},{t:'DELL',n:'Dell'},
  {t:'HPQ',n:'HP'},{t:'ROKU',n:'Roku'},{t:'ZM',n:'Zoom'},{t:'DOCU',n:'DocuSign'},{t:'TWLO',n:'Twilio'},
  // ── Payments / Fintech ──
  {t:'V',n:'Visa'},{t:'MA',n:'Mastercard'},{t:'PYPL',n:'PayPal'},{t:'SQ',n:'Block'},
  {t:'COIN',n:'Coinbase'},{t:'SOFI',n:'SoFi'},{t:'HOOD',n:'Robinhood'},{t:'AFRM',n:'Affirm'},
  {t:'FIS',n:'Fidelity National'},{t:'FISV',n:'Fiserv'},{t:'GPN',n:'Global Payments'},
  // ── Finance ──
  {t:'JPM',n:'JPMorgan'},{t:'BAC',n:'Bank of America'},{t:'GS',n:'Goldman Sachs'},{t:'MS',n:'Morgan Stanley'},
  {t:'C',n:'Citigroup'},{t:'WFC',n:'Wells Fargo'},{t:'SCHW',n:'Schwab'},{t:'BLK',n:'BlackRock'},
  {t:'AXP',n:'American Express'},{t:'COF',n:'Capital One'},{t:'USB',n:'U.S. Bancorp'},
  {t:'PNC',n:'PNC Financial'},{t:'TFC',n:'Truist'},{t:'BK',n:'BNY Mellon'},{t:'CME',n:'CME Group'},
  {t:'ICE',n:'Intercontinental Exchange'},{t:'SPGI',n:'S&P Global'},{t:'MCO',n:'Moody\'s'},
  // ── Healthcare ──
  {t:'UNH',n:'UnitedHealth'},{t:'LLY',n:'Eli Lilly'},{t:'JNJ',n:'Johnson & Johnson'},
  {t:'MRK',n:'Merck'},{t:'PFE',n:'Pfizer'},{t:'ABBV',n:'AbbVie'},{t:'TMO',n:'Thermo Fisher'},
  {t:'ABT',n:'Abbott Labs'},{t:'DHR',n:'Danaher'},{t:'BMY',n:'Bristol-Myers'},{t:'AMGN',n:'Amgen'},
  {t:'GILD',n:'Gilead'},{t:'REGN',n:'Regeneron'},{t:'VRTX',n:'Vertex'},{t:'ISRG',n:'Intuitive Surgical'},
  {t:'BSX',n:'Boston Scientific'},{t:'SYK',n:'Stryker'},{t:'ZBH',n:'Zimmer Biomet'},
  {t:'DXCM',n:'DexCom'},{t:'VEEV',n:'Veeva Systems'},{t:'ILMN',n:'Illumina'},
  {t:'CI',n:'Cigna'},{t:'CVS',n:'CVS Health'},{t:'HCA',n:'HCA Healthcare'},
  // ── Consumer ──
  {t:'HD',n:'Home Depot'},{t:'COST',n:'Costco'},{t:'WMT',n:'Walmart'},{t:'TGT',n:'Target'},
  {t:'LOW',n:'Lowe\'s'},{t:'TJX',n:'TJ Maxx'},{t:'ROST',n:'Ross Stores'},
  {t:'NKE',n:'Nike'},{t:'SBUX',n:'Starbucks'},{t:'MCD',n:'McDonald\'s'},{t:'CMG',n:'Chipotle'},
  {t:'YUM',n:'Yum! Brands'},{t:'DPZ',n:'Domino\'s'},{t:'DASH',n:'DoorDash'},
  {t:'KO',n:'Coca-Cola'},{t:'PEP',n:'PepsiCo'},{t:'MNST',n:'Monster Beverage'},
  {t:'PG',n:'Procter & Gamble'},{t:'CL',n:'Colgate'},{t:'KMB',n:'Kimberly-Clark'},
  {t:'DIS',n:'Disney'},{t:'NCLH',n:'Norwegian Cruise'},{t:'RCL',n:'Royal Caribbean'},{t:'MAR',n:'Marriott'},
  {t:'HLT',n:'Hilton'},{t:'BKNG',n:'Booking'},{t:'ABNB',n:'Airbnb'},
  {t:'LULU',n:'Lululemon'},{t:'ULTA',n:'Ulta Beauty'},{t:'ELF',n:'e.l.f. Beauty'},
  {t:'ETSY',n:'Etsy'},{t:'CHWY',n:'Chewy'},{t:'W',n:'Wayfair'},
  // ── Energy ──
  {t:'XOM',n:'ExxonMobil'},{t:'CVX',n:'Chevron'},{t:'COP',n:'ConocoPhillips'},
  {t:'SLB',n:'Schlumberger'},{t:'EOG',n:'EOG Resources'},{t:'PXD',n:'Pioneer Natural'},
  {t:'MPC',n:'Marathon Petroleum'},{t:'VLO',n:'Valero'},{t:'PSX',n:'Phillips 66'},
  {t:'OXY',n:'Occidental'},{t:'FANG',n:'Diamondback'},
  // ── Industrial ──
  {t:'CAT',n:'Caterpillar'},{t:'BA',n:'Boeing'},{t:'GE',n:'GE Aerospace'},{t:'HON',n:'Honeywell'},
  {t:'DE',n:'John Deere'},{t:'UPS',n:'UPS'},{t:'FDX',n:'FedEx'},{t:'RTX',n:'RTX'},
  {t:'LMT',n:'Lockheed Martin'},{t:'NOC',n:'Northrop Grumman'},{t:'GD',n:'General Dynamics'},
  {t:'EMR',n:'Emerson'},{t:'ITW',n:'Illinois Tool Works'},{t:'PH',n:'Parker Hannifin'},
  {t:'MMM',n:'3M'},{t:'WM',n:'Waste Management'},{t:'RSG',n:'Republic Services'},
  // ── Auto / EV ──
  {t:'F',n:'Ford'},{t:'GM',n:'General Motors'},{t:'RIVN',n:'Rivian'},{t:'NIO',n:'NIO'},
  {t:'LCID',n:'Lucid'},{t:'LI',n:'Li Auto'},{t:'XPEV',n:'XPeng'},
  // ── Social / Growth ──
  {t:'SNAP',n:'Snap'},{t:'PINS',n:'Pinterest'},{t:'UBER',n:'Uber'},{t:'LYFT',n:'Lyft'},
  {t:'RBLX',n:'Roblox'},{t:'U',n:'Unity'},{t:'DKNG',n:'DraftKings'},{t:'MTCH',n:'Match Group'},
  {t:'SHOP',n:'Shopify'},{t:'PLTR',n:'Palantir'},{t:'CVNA',n:'Carvana'},
  {t:'HIMS',n:'Hims & Hers'},{t:'CAVA',n:'CAVA Group'},{t:'DUOL',n:'Duolingo'},
  {t:'TOST',n:'Toast'},{t:'ONON',n:'On Holding'},{t:'BROS',n:'Dutch Bros'},
  // ── Crypto / Mining ──
  {t:'MSTR',n:'MicroStrategy'},{t:'MARA',n:'Marathon Digital'},{t:'RIOT',n:'Riot Platforms'},
  {t:'COIN',n:'Coinbase'},{t:'CLSK',n:'CleanSpark'},{t:'HUT',n:'Hut 8'},
  // ── Real Estate ──
  {t:'AMT',n:'American Tower'},{t:'PLD',n:'Prologis'},{t:'CCI',n:'Crown Castle'},
  {t:'EQIX',n:'Equinix'},{t:'SPG',n:'Simon Property'},{t:'O',n:'Realty Income'},
  // ── Telecom / Media ──
  {t:'T',n:'AT&T'},{t:'VZ',n:'Verizon'},{t:'TMUS',n:'T-Mobile'},{t:'CMCSA',n:'Comcast'},
  {t:'WBD',n:'Warner Bros'},{t:'PARA',n:'Paramount'},{t:'FOX',n:'Fox'},
  // ── Materials / Mining ──
  {t:'NEM',n:'Newmont Mining'},{t:'GOLD',n:'Barrick Gold'},{t:'FCX',n:'Freeport-McMoRan'},
  {t:'NUE',n:'Nucor'},{t:'STLD',n:'Steel Dynamics'},{t:'CLF',n:'Cleveland-Cliffs'},
  {t:'APD',n:'Air Products'},{t:'ECL',n:'Ecolab'},{t:'SHW',n:'Sherwin-Williams'},
  // ── Utilities ──
  {t:'NEE',n:'NextEra Energy'},{t:'SO',n:'Southern Company'},{t:'DUK',n:'Duke Energy'},
  {t:'D',n:'Dominion Energy'},{t:'AEP',n:'American Electric'},{t:'XEL',n:'Xcel Energy'},
  // ── Defense / Space ──
  {t:'LHX',n:'L3Harris'},{t:'AXON',n:'Axon Enterprise'},{t:'RKLB',n:'Rocket Lab'},
  // ── Biotech ──
  {t:'BIIB',n:'Biogen'},{t:'CELH',n:'Celsius'},{t:'MRNA',n:'Moderna'},
  // ── ETFs ──
  {t:'SPY',n:'S&P 500 ETF'},{t:'QQQ',n:'Nasdaq 100 ETF'},{t:'IWM',n:'Russell 2000 ETF'},
  {t:'DIA',n:'Dow Jones ETF'},{t:'ARKK',n:'ARK Innovation'},{t:'XLF',n:'Financial ETF'},
  {t:'XLE',n:'Energy ETF'},{t:'SOXX',n:'Semiconductor ETF'},{t:'XLK',n:'Tech ETF'},
  {t:'XLV',n:'Healthcare ETF'},{t:'XLI',n:'Industrial ETF'},{t:'GLD',n:'Gold ETF'},
  {t:'SLV',n:'Silver ETF'},{t:'TLT',n:'20yr Treasury ETF'},{t:'VIX',n:'Volatility Index'},
]

function AnalyzeView({ sendMessage, setView }) {
  const [ticker, setTicker] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [cachedPrices, setCachedPrices] = useState({})

  const lookup = async (t) => {
    if (!t) return
    setLoading(true); setSuggestions([])
    try {
      const r = await f(API + '/api/quick/' + t.toUpperCase()).then(r => r.json())
      if (r.ok) { setResult(r); setCachedPrices(prev => ({...prev, [r.ticker]: r})) }
      else setResult(null)
    } catch { setResult(null) }
    setLoading(false)
  }

  const onType = (val) => {
    const v = val.toUpperCase().replace(/[^A-Z.]/g, '')
    setTicker(v); setResult(null)
    if (v.length >= 2) {
      const matches = TICKER_DB.filter(s => s.t.startsWith(v) || s.n.toLowerCase().includes(val.toLowerCase())).slice(0, 8)
      setSuggestions(matches)
      // Fetch prices for visible suggestions
      matches.forEach(s => {
        if (!cachedPrices[s.t]) {
          f(API + '/api/quick/' + s.t).then(r => r.json()).then(r => {
            if (r.ok) setCachedPrices(prev => ({...prev, [r.ticker]: r}))
          }).catch(() => {})
        }
      })
    } else setSuggestions([])
  }

  const pick = (t) => { setTicker(t); setSuggestions([]); lookup(t) }

  return (
    <div className="view-scroll">
      <h2 className="view-h">Analyze</h2>
      <p className="view-sub">Look up any stock — price, score, signal, and chart.</p>

      <div className="az-search">
        <div className="az-input-wrap">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{color:'var(--dim)',flexShrink:0}}><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <input className="az-input" placeholder="Search a stock..." value={ticker}
            name="stock-search-field" autoComplete="off" autoCorrect="off" autoCapitalize="characters" spellCheck={false} data-1p-ignore data-lpignore="true" data-form-type="other"
            onChange={e => onType(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && ticker) { setSuggestions([]); lookup(ticker) }}}
            autoFocus/>
          {loading && <span className="az-spin">...</span>}
        </div>
        {suggestions.length > 0 && <div className="az-suggest">
          {suggestions.map(s => {
            const c = cachedPrices[s.t]
            return <button key={s.t} className="az-sug" onClick={() => pick(s.t)}>
              <span className="az-sug-t">{s.t}</span>
              <span className="az-sug-n">{s.n}</span>
              <span className="az-sug-line"/>
              {c ? <>
                <span className={'az-sug-p '+(c.change>=0?'up':'dn')}>${c.price}</span>
                <span className={'az-sug-c '+(c.change>=0?'up':'dn')}>{c.change>=0?'+':''}{c.change_pct}%</span>
              </> : <span className="az-sug-loading">···</span>}
            </button>
          })}
        </div>}
      </div>

      {result && result.delisted && <div className="az-result">
        <div className="az-card">
          <div className="az-top">
            <div className="az-top-l">
              <div className="az-id">
                <span className="az-sym">{result.ticker}</span>
                <span className="az-signal az-avoid">DELISTED</span>
              </div>
              {result.company&&result.company.name&&<div className="az-co-name">{result.company.name}{result.company.sector&&<span className="az-co-sector">{result.company.sector}</span>}</div>}
            </div>
          </div>
          <div className="az-newnote">
            {result.ticker} is no longer trading — it looks like the stock has been delisted, acquired, or halted (no new price data for {result.stale_days||'several'} days). You can't analyze or trade it. If you held shares, your broker will convert them per the corporate action.
          </div>
        </div>
      </div>}

      {result && result.too_new && <div className="az-result">
        <div className="az-card">
          <div className="az-top">
            <div className="az-top-l">
              <div className="az-id">
                <span className="az-sym">{result.ticker}</span>
                <span className="az-signal az-new">TOO NEW</span>
              </div>
              {result.company&&result.company.name&&<div className="az-co-name">{result.company.name}{result.company.sector&&<span className="az-co-sector">{result.company.sector}</span>}</div>}
            </div>
            <div className="az-price-wrap">
              <span className="az-price">${result.price}</span>
            </div>
          </div>
          {result.company&&(result.company.ceo||result.company.summary)&&<div className="az-company">
            {result.company.ceo&&<div className="az-co-ceo"><span className="az-co-k">CEO</span>{result.company.ceo}</div>}
            {result.company.summary&&<p className="az-co-sum">{result.company.summary}</p>}
          </div>}
          <div className="az-newnote">
            Not enough trading history to analyze yet{typeof result.history_days==='number'?` — only ${result.history_days} day${result.history_days===1?'':'s'} of data`:''}. The signal engine needs at least ~50 days of price action (for moving averages, RSI, trend, and volume) before it can score a setup. Check back once it's been trading longer.
          </div>
        </div>
      </div>}

      {result && !result.too_new && !result.delisted && <div className="az-result">
        <div className="az-card">
          <div className="az-top">
            <div className="az-top-l">
              <div className="az-id">
                <span className="az-sym">{result.ticker}</span>
                <span className={'az-signal az-'+result.signal.toLowerCase()}>{result.signal} · {result.score}</span>
              </div>
              {result.company&&result.company.name&&<div className="az-co-name">{result.company.name}{result.company.sector&&<span className="az-co-sector">{result.company.sector}</span>}</div>}
            </div>
            <div className="az-price-wrap">
              <span className="az-price">${result.price}</span>
              <span className={'az-chg '+(result.change>=0?'up':'dn')}>{result.change>=0?'+':''}{result.change} ({result.change_pct}%)</span>
            </div>
          </div>

          {result.company&&(result.company.ceo||result.company.summary)&&<div className="az-company">
            {result.company.ceo&&<div className="az-co-ceo"><span className="az-co-k">CEO</span>{result.company.ceo}</div>}
            {result.company.summary&&<p className="az-co-sum">{result.company.summary}</p>}
          </div>}
        </div>

        <div className="az-chart"><Suspense fallback={<ChartFallback/>}><Chart ticker={result.ticker} height={320}/></Suspense></div>

        {result.reasons&&result.reasons.length>0&&<div className="az-why">
          <div className="az-why-h">Why this score</div>
          <ul className="az-why-list">{result.reasons.map((r,i)=><li key={i}>{r}</li>)}</ul>
        </div>}

        <div className="az-actions"><button className="az-btn az-deep" onClick={()=>{sendMessage('Analyze '+result.ticker);setView('chat')}}>Deep dive in chat →</button></div>
      </div>}

    </div>
  )
}

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
      else setMlInsights({ error: r.error || 'No data available' })
    } catch { setMlInsights({ error: 'Failed to connect' }) }
    setMlLoading(false)
  }

  const s = result?.stats
  return (
    <div className="view-scroll">
      <h2 className="view-h">Backtest</h2>

      <div className="bt-actions">
        <button className="bt-run" onClick={runBacktest} disabled={loading}>
          {loading ? 'Running…' : 'Run 90-day backtest'}
        </button>
        <button className="bt-run bt-ml" onClick={runML} disabled={mlLoading}>
          {mlLoading ? 'Training…' : 'Analyze trades'}
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
          {mlInsights.error ? (
            <div className="view-msg" style={{padding:'20px 0'}}>{mlInsights.error}</div>
          ) : (<>
          <label>ML insights — {mlInsights.total_trades} trades analyzed</label>
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
          </>)}
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
      <Suspense fallback={<ChartFallback/>}><Chart key={safeTicker} ticker={safeTicker} signal={active === 0 ? signal : null} height={240} /></Suspense>
    </div>
  )
}

function SignalCard({ data, onExecute }) {
  if (!data) return null
  const scores = data.scores || {}
  const trade = data.trade || {}
  const side = trade.side
  const isBuy = side === 'LONG'
  const isExit = side === 'EXIT'
  const isAvoid = side === 'AVOID'
  const isNeutral = side === 'NEUTRAL'

  const ScoreBar = ({ name, sub, value }) => {
    const color = value >= 70 ? 'var(--grn)' : value >= 50 ? 'var(--amb)' : 'var(--red)'
    return (
      <div className="sc-row">
        <div className="sc-label"><span className="sc-name">{name}</span><span className="sc-sub">{sub}</span></div>
        <div className="sc-bar-wrap">
          <div className="sc-bar" style={{ width: value + '%', background: color }}/>
        </div>
        <span className="sc-val" style={{ color }}>{value}</span>
      </div>
    )
  }

  return (
    <div className="signal-card">
      {/* Score bars */}
      <div className="sc-scores">
        <div className="sc-header">SETUP SCORES</div>
        {scores.trend && <ScoreBar name="Trend" sub={scores.trend.label} value={scores.trend.value}/>}
        {scores.momentum && <ScoreBar name="Momentum" sub={scores.momentum.label} value={scores.momentum.value}/>}
        {scores.mean_reversion && <ScoreBar name="Mean-reversion" sub={scores.mean_reversion.label} value={scores.mean_reversion.value}/>}
        {scores.news && <ScoreBar name="News sentiment" sub={scores.news.label} value={scores.news.value}/>}
      </div>

      {/* Bearish banner — show indicative levels (short framing) */}
      {(isExit || isAvoid) && (
        <div className={'sc-trade ' + (isExit ? 'sc-sell' : '')}>
          <div className="sc-trade-head">
            <div className="sc-trade-left">
              <span className={'sc-side sc-side-sell'}>{isExit ? 'EXIT' : 'AVOID'}</span>
              <span className="sc-ticker">{data.ticker}</span>
            </div>
            <span className="sc-rr">Score <b>{data.score}</b></span>
          </div>
          <div className="sc-warn">
            {isExit
              ? (trade.holds_long
                  ? 'Signal has turned bearish on a position you hold. Consider closing the long — this is not a setup to short.'
                  : 'Bearish signal. If you hold this, consider exiting — this is not a short-entry setup.')
              : 'Bearish signal and you don\u2019t hold it. Best action is to stay flat — no long entry here.'}
          </div>
          {trade.entry > 0 && trade.stop > 0 && trade.target > 0 && (
            <div className="sc-levels">
              <div className="sc-level"><span className="sc-level-l">REF</span><span className="sc-level-v">${trade.entry?.toFixed(2)}</span></div>
              <div className="sc-level"><span className="sc-level-l">STOP</span><span className="sc-level-v sc-stop">${trade.stop?.toFixed(2)}</span></div>
              <div className="sc-level"><span className="sc-level-l">TARGET</span><span className="sc-level-v sc-target">${trade.target?.toFixed(2)}</span></div>
            </div>
          )}
          {data.earnings_warning && <div className="sc-warn">⚠ {data.earnings_warning}</div>}
          {isExit && (
            <div className="sc-actions">
              <button className="sc-btn sc-exec" onClick={() => onExecute(data.ticker, 'EXIT')}>Close position</button>
            </div>
          )}
        </div>
      )}

      {/* Neutral / HOLD — show indicative levels (no execute button) */}
      {isNeutral && trade.entry > 0 && trade.stop > 0 && trade.target > 0 && (
        <div className="sc-trade">
          <div className="sc-trade-head">
            <div className="sc-trade-left">
              <span className="sc-side">HOLD</span>
              <span className="sc-ticker">{data.ticker}</span>
            </div>
            <span className="sc-rr">Score <b>{data.score}</b></span>
          </div>
          <div className="sc-warn">No high-conviction entry right now — these are indicative levels if the setup develops.</div>
          <div className="sc-levels">
            <div className="sc-level"><span className="sc-level-l">REF</span><span className="sc-level-v">${trade.entry?.toFixed(2)}</span></div>
            <div className="sc-level"><span className="sc-level-l">STOP</span><span className="sc-level-v sc-stop">${trade.stop?.toFixed(2)}</span></div>
            <div className="sc-level"><span className="sc-level-l">TARGET</span><span className="sc-level-v sc-target">${trade.target?.toFixed(2)}</span></div>
          </div>
          {data.earnings_warning && <div className="sc-warn">⚠ {data.earnings_warning}</div>}
        </div>
      )}

      {/* Long trade card */}
      {isBuy && trade.entry > 0 && (
        <div className="sc-trade sc-buy">
          <div className="sc-trade-head">
            <div className="sc-trade-left">
              <span className="sc-side sc-side-buy">LONG</span>
              <span className="sc-ticker">{data.ticker}</span>
            </div>
            <span className="sc-rr">R:R · <b>{trade.rr?.toFixed(1)}</b></span>
          </div>
          <div className="sc-levels">
            <div className="sc-level"><span className="sc-level-l">ENTRY</span><span className="sc-level-v">${trade.entry?.toFixed(2)}</span></div>
            <div className="sc-level"><span className="sc-level-l">STOP</span><span className="sc-level-v sc-stop">${trade.stop?.toFixed(2)}</span></div>
            <div className="sc-level"><span className="sc-level-l">TARGET</span><span className="sc-level-v sc-target">${trade.target?.toFixed(2)}</span></div>
          </div>
          {data.earnings_warning && <div className="sc-warn">⚠ {data.earnings_warning}</div>}
          <div className="sc-actions">
            <button className="sc-btn sc-exec" onClick={() => onExecute(data.ticker, 'LONG')}>Execute</button>
          </div>
        </div>
      )}
    </div>
  )
}

function AdminPanel({ token, onClose }) {
  const [users, setUsers] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [maintOn, setMaintOn] = useState(false)
  const [maintMsg, setMaintMsg] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const [u, s, m] = await Promise.all([
          f(API + '/api/admin/users', { headers: { Authorization: 'Bearer ' + token } }).then(r => r.json()),
          f(API + '/api/admin/stats', { headers: { Authorization: 'Bearer ' + token } }).then(r => r.json()),
          f(API + '/api/maintenance').then(r => r.json()),
        ])
        if (u.ok) setUsers(u.users)
        if (s.ok) setStats(s)
        if (m.ok) { setMaintOn(m.on); setMaintMsg(m.message || '') }
      } catch {
        // network/parse error — leave existing data, just stop the spinner
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const toggleMaint = async (on) => {
    setMaintOn(on)
    await f(API + '/api/admin/maintenance', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify({ on, message: maintMsg })
    }).catch(() => {})
  }

  const togglePlus = async (u) => {
    const on = !u.plus
    setUsers(prev => prev.map(x => x.id === u.id ? { ...x, plus: on } : x))
    await f(API + '/api/admin/set-plus', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify({ user_id: u.id, on })
    }).catch(() => {})
  }

  const deleteUser = async (id, name) => {
    if (!confirm('Delete user "' + name + '" and all their data?')) return
    const r = await f(API + '/api/admin/users/' + id, { method: 'DELETE', headers: { Authorization: 'Bearer ' + token } }).then(r => r.json())
    if (r.ok) setUsers(prev => prev.filter(u => u.id !== id))
  }

  const clearAll = async () => {
    if (!confirm('DELETE all users except you? This cannot be undone.')) return
    const r = await f(API + '/api/admin/clear-all', { method: 'POST', headers: { Authorization: 'Bearer ' + token } }).then(r => r.json())
    if (r.ok) { setUsers(prev => prev.filter(u => u.email === 'parjan.d@icloud.com')); alert('Cleared. ' + r.remaining + ' user(s) remaining.') }
  }

  return (
    <div className="cl-overlay" onClick={onClose}>
      <div className="cl-modal" onClick={e => e.stopPropagation()} style={{width: 600, maxHeight: '80vh'}}>
        <div className="cl-head"><span className="cl-ver-title">Admin Panel</span><button className="cl-x" onClick={onClose}>×</button></div>
        <div className="cl-pad" style={{overflowY: 'auto'}}>
          <div style={{background: maintOn?'rgba(245,158,11,.12)':'var(--c2)', border:'1px solid '+(maintOn?'#f5a623':'var(--brd)'), borderRadius:10, padding:'14px 16px', marginBottom:16}}>
            <div style={{display:'flex',alignItems:'center',gap:12}}>
              <div style={{flex:1}}>
                <div style={{fontWeight:700,fontSize:'.8rem',color: maintOn?'#f5a623':'var(--wh)'}}>Maintenance mode {maintOn?'· ON':''}</div>
                <div style={{fontSize:'.6rem',color:'var(--dim)',marginTop:2}}>Blocks the app for everyone except you.</div>
              </div>
              <button onClick={() => toggleMaint(!maintOn)} style={{background: maintOn?'#f5a623':'var(--grn)', border:'none', borderRadius:8, padding:'8px 18px', color:'#04130d', fontSize:'.7rem', fontWeight:700, cursor:'pointer'}}>{maintOn ? 'Turn off' : 'Turn on'}</button>
            </div>
            <input value={maintMsg} onChange={e => setMaintMsg(e.target.value)} onBlur={() => maintOn && toggleMaint(true)} placeholder="Optional message shown to users…" style={{marginTop:10,width:'100%',background:'var(--c1)',border:'1px solid var(--brd)',borderRadius:8,padding:'8px 12px',color:'var(--lt)',fontSize:'.72rem'}} />
          </div>
          {stats && <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:8,marginBottom:16}}>
            <div className="card"><div className="stat-sub">Users</div><div className="stat-n">{stats.total_users}</div></div>
            <div className="card"><div className="stat-sub">Messages</div><div className="stat-n">{stats.total_messages}</div></div>
            <div className="card"><div className="stat-sub">Sessions</div><div className="stat-n">{stats.active_sessions}</div></div>
            <div className="card"><div className="stat-sub">Autopilot</div><div className="stat-n">{stats.autopilot_active ? 'ON' : 'OFF'}</div></div>
          </div>}

          <div style={{display:'flex',alignItems:'center',marginBottom:8}}>
            <span style={{fontSize:'.52rem',textTransform:'uppercase',letterSpacing:'.12em',color:'var(--dim)',fontWeight:700}}>Accounts</span>
            <button onClick={clearAll} style={{marginLeft:'auto',background:'none',border:'1px solid var(--red)',borderRadius:6,padding:'4px 12px',color:'var(--red)',fontSize:'.5rem',fontWeight:600,cursor:'pointer'}}>Clear all users</button>
          </div>
          {loading ? <div style={{color:'var(--dim)',padding:20}}>Loading...</div> :
          <div style={{display:'flex',flexDirection:'column',gap:4}}>
            {users.map(u => (
              <div key={u.id} style={{display:'flex',alignItems:'center',gap:12,padding:'10px 12px',background:'var(--c2)',borderRadius:8}}>
                <span style={{fontFamily:'var(--mono)',fontWeight:700,color:'var(--wh)',fontSize:'.76rem',minWidth:80}}>{u.username}</span>
                <span style={{fontSize:'.56rem',color:'var(--dim)',flex:1}}>{u.email || 'no email'}</span>
                <span style={{fontFamily:'var(--mono)',fontSize:'.52rem',color:'var(--dim)'}}>{u.messages} msgs</span>
                <span style={{fontSize:'.48rem',color:'var(--dim)'}}>{u.last_login ? new Date(u.last_login).toLocaleDateString() : 'never'}</span>
                <button onClick={() => togglePlus(u)} style={{background: u.plus?'var(--grn)':'none', border:'1px solid '+(u.plus?'var(--grn)':'var(--brd)'), borderRadius:6, padding:'4px 10px', color: u.plus?'#04130d':'var(--lt)', fontSize:'.52rem', fontWeight:700, cursor:'pointer'}}>{u.plus?'Plus ✓':'Grant Plus'}</button>
                <button onClick={() => deleteUser(u.id, u.username)} style={{background:'none',border:'1px solid var(--brd)',borderRadius:6,padding:'4px 10px',color:'var(--red)',fontSize:'.52rem',fontWeight:600,cursor:'pointer'}}>Delete</button>
              </div>
            ))}
          </div>}
        </div>
      </div>
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
    try { const r = await f(API+'/api/performance?period='+p+'&_t='+Date.now()).then(r=>r.json()); if(r.ok)setData(r) } catch{}
  }
  // Always fetch fresh on mount (not just rely on the cached perf prop) so the
  // Auto-Tuner Config panel reflects the live backend config.
  useEffect(()=>{
    (async()=>{ try { const r = await f(API+'/api/performance?period=1M&_t='+Date.now()).then(r=>r.json()); if(r.ok)setData(r) } catch{} })()
  },[])
  useEffect(()=>{if(perf)setData(perf)},[perf])
  const d = data || perf
  if(!d)return <div className="view-msg">Loading...</div>

  const startEq = d.pnl_history?.[0]?.equity || 0
  const endEq = d.pnl_history?.[d.pnl_history.length-1]?.equity || 0
  const totalChg = endEq - startEq
  const totalPct = startEq > 0 ? ((endEq/startEq - 1)*100) : 0

  return(<div className="view-scroll"><h2 className="view-h">Performance</h2>
    <p className="view-sub">Trailing {period} · Updated {new Date().toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZone:'America/New_York'})} ET</p>
    {/* Period selector */}
    <div className="period-bar">
      {[['1D','1D'],['1W','1W'],['1M','1M'],['3M','3M'],['6M','6M'],['1A','YTD'],['all','ALL']].map(([k,label])=>(
        <button key={k} className={'per-btn'+(period===k?' per-on':'')} onClick={()=>loadPeriod(k)}>{label}</button>
      ))}
    </div>

    {/* Equity chart card */}
    <div className="eq-card">
      <div className="eq-header">
        <div>
          <span className="eq-title">PORTFOLIO VALUE</span>
          <span className="eq-value">${(d.equity||endEq||0).toLocaleString(undefined,{maximumFractionDigits:0})}</span>
        </div>
        <div className="eq-change">
          <span className={(totalChg>=0?'up':'dn')+' eq-chg'}>{totalChg>=0?'+':'−'}${Math.abs(totalChg).toFixed(0)}</span>
          <span className={(totalPct>=0?'up':'dn')+' eq-pct'}>{totalPct>=0?'+':''}{totalPct.toFixed(2)}% · {period}</span>
        </div>
      </div>
      {d.pnl_history?.length>1 ? <EqChart data={d.pnl_history}/> : <div className="eq-empty">No data for this period</div>}
    </div>

    {/* Stats row — matching reference */}
    <div className="stat-row">
      <div className="stat-card"><span className="stat-l">WIN RATE</span><span className="stat-n">{d.win_rate||'0'}%</span><span className="stat-sub">{d.wins||0} of {d.total_trades||0} trades</span></div>
      <div className="stat-card"><span className="stat-l">AVG R</span><span className="stat-n">{d.avg_rr||'1.00'}</span><span className="stat-sub">target 1.5R+</span></div>
      <div className="stat-card"><span className="stat-l">BEST DAY</span><span className="stat-n up">+${d.best_day_pnl||0}</span><span className="stat-sub">{d.best_day_date||'—'} · {d.best_day_ticker||''}</span></div>
      <div className="stat-card"><span className="stat-l">WORST DAY</span><span className="stat-n dn">−${Math.abs(d.worst_day_pnl||0)}</span><span className="stat-sub">{d.worst_day_date||'—'} · {d.worst_day_ticker||''}</span></div>
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

function SetView({settings,update,user,token,logout,autopilot,setAutopilot,persist,setActiveChatId,setMessages,setShowChangelog,setUser,theme,setTheme,setView}){
  const [keys, setKeys] = useState({alpaca_key:'',alpaca_secret:'',groq_key:'',polygon_key:''})
  const [keyExists, setKeyExists] = useState({alpaca_key:false,alpaca_secret:false,groq_key:false,polygon_key:false})
  const [keySaved, setKeySaved] = useState(false)
  const [keyLoaded, setKeyLoaded] = useState(false)
  const [showAdmin, setShowAdmin] = useState(false)
  const [showPlus, setShowPlus] = useState(false)
  const isPlus = !!(user && (user.plus || user.is_admin))

  useEffect(()=>{
    if(token&&!keyLoaded){
      f(API+'/api/auth/me').then(r=>r.json()).then(d=>{
        if(d.ok&&d.settings){
          // Never load the actual secret values into the inputs — only note
          // which ones are already saved, so we can show a masked placeholder.
          setKeyExists({
            alpaca_key: !!(d.settings.alpaca_key_set || d.settings.alpaca_key),
            alpaca_secret: !!(d.settings.alpaca_secret_set || d.settings.alpaca_secret),
            groq_key: !!d.settings.groq_key,
            polygon_key: !!d.settings.polygon_key,
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
    if(res.ok){
      // Mark any just-entered keys as saved, then clear the inputs so secrets
      // don't linger on screen.
      setKeyExists(prev=>({
        alpaca_key: prev.alpaca_key || !!keys.alpaca_key,
        alpaca_secret: prev.alpaca_secret || !!keys.alpaca_secret,
        groq_key: prev.groq_key || !!keys.groq_key,
        polygon_key: prev.polygon_key || !!keys.polygon_key,
      }))
      setKeys({alpaca_key:'',alpaca_secret:'',groq_key:'',polygon_key:''})
      setKeySaved(true);setTimeout(()=>setKeySaved(false),2000)
    }
  }

  const fontSizes = [{name:'Small',val:'13px',display:11},{name:'Default',val:'15px',display:15},{name:'Large',val:'18px',display:19}]

  return(<div className="view-scroll"><h2 className="view-h">Settings</h2>
    <p className="view-sub">Account, integrations, and behavior</p>

    {/* Connections */}
    {user&&<div className="card wide"><label>Connections</label><span className="card-sub">Broker and data feeds</span>
      <p className="s-hint">Add your own Alpaca paper keys to trade <b>your own account</b>. Leave blank to use the shared demo account. Keys are encrypted and never shown again.</p>
      <div className="s-row"><div className="s-col"><span>Alpaca Key</span><span className="s-desc">Broker · trade execution</span></div><input className="s-inp s-wide" type="password" name="alpaca-key-field" autoComplete="off" data-1p-ignore data-lpignore="true" data-form-type="other" value={keys.alpaca_key} onChange={e=>setKeys({...keys,alpaca_key:e.target.value})} placeholder={keyExists.alpaca_key?'•••••••• saved — leave blank to keep':'PKSPW...'}/></div>
      <div className="s-row"><div className="s-col"><span>Alpaca Secret</span><span className="s-desc">From your Alpaca dashboard</span></div><input className="s-inp s-wide" type="password" name="alpaca-secret-field" autoComplete="off" data-1p-ignore data-lpignore="true" data-form-type="other" value={keys.alpaca_secret} onChange={e=>setKeys({...keys,alpaca_secret:e.target.value})} placeholder={keyExists.alpaca_secret?'•••••••• saved — leave blank to keep':'AzMr...'}/></div>
      <button className={'login-btn s-save'+(keySaved?' s-saved':'')} onClick={saveKeys}>{keySaved?'✓ Saved':'Save connections'}</button>
    </div>}

    {/* Appearance */}
    <div className="card wide"><label>Appearance</label>
      <div className="s-row"><span>Theme</span>
        <div className="theme-picks">
          <button className={'tp-btn'+(theme!=='light'?' tp-on':'')} onClick={()=>setTheme&&setTheme('dark')}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            <span>Dark</span>
          </button>
          <button className={'tp-btn'+(theme==='light'?' tp-on':'')} onClick={()=>setTheme&&setTheme('light')}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/></svg>
            <span>Light</span>
          </button>
        </div>
      </div>
      <div className="s-row"><span>Font Size</span>
        <div className="font-picks">
          {fontSizes.map(s=>(
            <button key={s.val} className={'fp-btn'+(settings.fontSize===s.val||(!settings.fontSize&&s.val==='15px')?' fp-on':'')}
              onClick={()=>{update('fontSize',s.val);document.documentElement.style.setProperty('--chat-fs',s.val)}}>
              <span className="fp-aa" style={{fontSize:s.display+'px'}}>Aa</span>
              <span className="fp-label">{s.name}</span>
            </button>
          ))}
        </div>
      </div>
    </div>

    {/* Sounds */}
    <div className="card wide"><label>Sounds</label>
      <Tog l="Trade sounds" on={settings.sounds!==false} fn={()=>update('sounds',!(settings.sounds!==false))}/>
      <Tog l="Scan notification" on={settings.scanSound!==false} fn={()=>update('scanSound',!(settings.scanSound!==false))}/>
    </div>

    

    

    

    {/* About */}
    <div className="card wide"><label>About</label>
      <div className="s-row"><span>Version</span><span className="s-ver">v{VERSION} <span className="s-build">{__BUILD_COMMIT__}</span></span></div>
      <div className="s-row"><span>Paula Plus</span>{isPlus?<span className="s-plus-on">✓ Active</span>:<button className="tog s-upgrade" onClick={() => setView && setView('plus')}>View plans →</button>}</div>
      {(user.email||'').toLowerCase() === 'parjan.d@icloud.com' && <div className="s-row"><span>Admin</span><button className="tog" onClick={() => setShowAdmin(true)}>Open panel</button></div>}
      {showAdmin && <AdminPanel token={token} onClose={() => setShowAdmin(false)}/>}
      {showPlus && <PlusModal token={token} onClose={() => setShowPlus(false)} onUnlocked={() => setUser && setUser(u => ({ ...u, plus: true }))}/>}
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

function fmt(t){
  if(!t)return '';
  // PERMANENT GUARD: the LLM sometimes hallucinates trade levels and repeats the
  // current price as entry, stop AND target. Trade levels come only from the
  // structured SignalCard, never LLM prose. Drop any line that (a) is a
  // structured "Entry/Stop/Target" line with zero/missing or all-equal numbers,
  // or (b) mentions an entry AND a stop/target where the two prices are equal.
  t = t.split('\n').filter(line => {
    const struct = line.match(/entry[:\s]*\$?([\d.,]+).*stop[:\s]*\$?([\d.,]+).*target[:\s]*\$?([\d.,]+)/i)
    if (struct) {
      const nums = [struct[1], struct[2], struct[3]].map(n => parseFloat(n.replace(/,/g, '')))
      if (nums.some(n => !isFinite(n) || n === 0)) return false
      const [a, b, c] = nums
      if (Math.abs(a - b) < 0.01 && Math.abs(b - c) < 0.01) return false
      return true
    }
    // prose form: "entry at $191.2 ... stop loss ... at $191.20" with equal prices
    if (/\bentry\b/i.test(line) && /(stop|target)/i.test(line)) {
      const prices = (line.match(/\$\s?([\d,]+\.?\d*)/g) || []).map(p => parseFloat(p.replace(/[$,\s]/g, '')))
      if (prices.length >= 2) {
        const uniq = [...new Set(prices.map(p => Math.round(p * 100)))]
        if (uniq.length === 1) return false  // all the same price → hallucination
      }
    }
    return true
  }).join('\n')
  if(!t.trim())return '';
  let s = t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  // Markdown links [label](url) -> compact anchor
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_,label,url)=>`<a href="${url}" target="_blank" rel="noopener noreferrer" class="ai-link">${label}</a>`);
  // Bare URLs -> clickable, labeled by domain (compact, not the full URL)
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s)]+)/g, (m,pre,url)=>{
    let host=url; try{ host=new URL(url).hostname.replace(/^www\./,''); }catch{}
    return `${pre}<a href="${url}" target="_blank" rel="noopener noreferrer" class="ai-link">${host}</a>`;
  });
  s = s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
       .replace(/`(.+?)`/g,'<code>$1</code>')
       .replace(/\n/g,'<br/>');
  return s;
}
export default App
