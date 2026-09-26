import {
  Bug,
  Gift,
  CalendarDays,
  FlaskConical,
  ChartCandlestick,
  LogOut,
  Menu,
  Search,
  MessageSquare,
  Settings,
  ShieldCheck,
  Sparkles,
  SquarePen,
  Trash2,
  Wallet,
  X,
  type LucideIcon,
} from 'lucide-react'
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { ChatScreen } from '../features/chat/ChatScreen'
import { ReportSheet } from '../features/feedback/ReportSheet'
import { PlusSheet } from '../features/plus/PlusSheet'
import { GiftSheet } from '../features/plus/GiftSheet'
import { WelcomeSheet } from '../features/plus/WelcomeSheet'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import { CommandPalette } from '../components/CommandPalette'
import { ThemeSwitch } from '../components/ThemeSwitch'
import type { ChatMessage } from '../lib/api'
import { useSession } from '../lib/auth'
import { ChatsProvider, useChats } from '../lib/chats'
import { ChromeContext, useChrome, type Chrome } from '../lib/chrome'
import { ToastProvider, useToast } from '../lib/toast'
import { VERSION } from '../lib/changelog'
import './shell.css'

// Chat is the landing screen; the chart-heavy and owner-only screens load on
// first visit so they don't weigh down the first paint.
const loadWhatsNew = () => import('../features/whatsnew/WhatsNewSheet')
const WhatsNewSheet = lazy(() => loadWhatsNew().then((m) => ({ default: m.WhatsNewSheet })))
const SEEN_KEY = 'paula-seen-version'

function unseenRelease(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) !== VERSION
  } catch {
    return false
  }
}

const loadAdmin = () => import('../features/admin/AdminScreen')
const loadAnalyze = () => import('../features/analyze/AnalyzeScreen')
const loadEarnings = () => import('../features/earnings/EarningsScreen')
const loadPortfolio = () => import('../features/portfolio/PortfolioScreen')
const loadLab = () => import('../features/lab/LabScreen')
const AdminScreen = lazy(() => loadAdmin().then((m) => ({ default: m.AdminScreen })))
const AnalyzeScreen = lazy(() => loadAnalyze().then((m) => ({ default: m.AnalyzeScreen })))
const EarningsScreen = lazy(() => loadEarnings().then((m) => ({ default: m.EarningsScreen })))
const PortfolioScreen = lazy(() => loadPortfolio().then((m) => ({ default: m.PortfolioScreen })))
const LabScreen = lazy(() => loadLab().then((m) => ({ default: m.LabScreen })))

// Once the first screen has painted and the browser is idle, fetch the other
// screens' code so switching tabs never waits on a download.
function preloadScreens(isAdmin: boolean) {
  const run = () => {
    void loadAnalyze()
    void loadPortfolio()
    void loadEarnings()
    if (isAdmin) {
      void loadAdmin()
      void loadLab()
    }
  }
  if ('requestIdleCallback' in window) window.requestIdleCallback(run, { timeout: 3000 })
  else setTimeout(run, 1500)
}

type View = 'chat' | 'analyze' | 'portfolio' | 'earnings' | 'lab' | 'settings' | 'admin'

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

const PRIMARY: { id: View; label: string; icon: LucideIcon }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'analyze', label: 'Analyze', icon: ChartCandlestick },
  { id: 'portfolio', label: 'Portfolio', icon: Wallet },
  { id: 'earnings', label: 'Earnings', icon: CalendarDays },
]

// Admin-only tools.
const LAB_NAV: typeof PRIMARY = [{ id: 'lab', label: 'Backtest lab', icon: FlaskConical }]

const TITLES: Record<View, string> = {
  chat: 'Chat',
  analyze: 'Analyze',
  portfolio: 'Portfolio',
  earnings: 'Earnings',
  lab: 'Backtest lab',
  settings: 'Settings',
  admin: 'Admin',
}

export function Shell() {
  const { user } = useSession()
  const [view, setView] = useState<View>('chat')
  const [palette, setPalette] = useState(false)
  const [analyzeReq, setAnalyzeReq] = useState<{ ticker: string; n: number } | null>(null)
  const [draft, setDraft] = useState<{ text: string; n: number } | null>(null)
  const [whatsNew, setWhatsNew] = useState(false)
  const [unseen, setUnseen] = useState(unseenRelease)

  const openWhatsNew = useCallback(() => {
    setWhatsNew(true)
    setUnseen(false)
    try {
      localStorage.setItem(SEEN_KEY, VERSION)
    } catch {
      /* ignore */
    }
  }, [])

  // Show release notes once per new version (not over the sign-up welcome).
  useEffect(() => {
    if (!unseenRelease()) return
    let welcoming = false
    try {
      welcoming = localStorage.getItem('paula-v2-welcome') === '1'
    } catch {
      /* ignore */
    }
    if (welcoming) return
    const t = setTimeout(openWhatsNew, 1200)
    return () => clearTimeout(t)
  }, [openWhatsNew])

  useEffect(() => preloadScreens(!!user?.is_admin), [user?.is_admin])

  // Tab title follows the page, like "Portfolio · Paula".
  useEffect(() => {
    document.title = view === 'chat' ? 'Paula' : `${TITLES[view]} · Paula`
  }, [view])

  // ⌘K / Ctrl+K anywhere opens the command menu.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPalette((p) => !p)
        return
      }
      // "/" jumps to the page's main input (chat box or ticker search),
      // unless you're already typing somewhere.
      const el = e.target as HTMLElement
      const typing = el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)
      if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) {
        const target = document.querySelector<HTMLElement>('.composer-input, .analyze-input')
        if (target) {
          e.preventDefault()
          target.focus()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const [drawer, setDrawer] = useState(false)
  const [plusOpen, setPlusOpen] = useState(false)
  const [report, setReport] = useState<{ open: boolean; transcript?: ChatMessage[] }>({ open: false })

  const chrome = useMemo<Chrome>(
    () => ({
      openPlus: () => setPlusOpen(true),
      openReport: (transcript) => setReport({ open: true, transcript }),
      openWhatsNew,
      askPaula: (text) => {
        setDraft((d) => ({ text, n: (d?.n ?? 0) + 1 }))
        setView('chat')
        setDrawer(false)
      },
      analyze: (ticker) => {
        setDraft(null)
        setAnalyzeReq((r) => ({ ticker: ticker.toUpperCase(), n: (r?.n ?? 0) + 1 }))
        setView('analyze')
        setDrawer(false)
      },
    }),
    [openWhatsNew],
  )

  function go(v: View) {
    setView(v)
    setDrawer(false)
    // A handed-over draft is one-shot: don't refill the box on a later visit.
    if (v !== 'chat') setDraft(null)
  }

  return (
    <ChromeContext.Provider value={chrome}>
      <ToastProvider>
        {/* Keyed per account so signing in/out swaps to that account's chats. */}
        <ChatsProvider key={user ? `u${user.id}` : 'guest'}>
          <div className={'app' + (drawer ? ' app-drawer-open' : '')}>
            <Sidebar
              view={view}
              go={go}
              unseen={unseen}
              onClose={() => setDrawer(false)}
              onSearch={() => {
                setDrawer(false)
                setPalette(true)
              }}
            />
            <div className="app-scrim" onClick={() => setDrawer(false)} />

            <div className="app-main">
              <header className="app-topbar">
                <button className="btn btn-ghost btn-icon" onClick={() => setDrawer(true)} aria-label="Open menu">
                  <Menu size={18} />
                </button>
                <span className="app-topbar-title">{TITLES[view]}</span>
              </header>

              <main className="app-content">
                <Suspense fallback={null}>
                  {view === 'chat' && <ChatScreen onNavigateAnalyze={() => go('analyze')} draft={draft} />}
                  {view === 'analyze' && <AnalyzeScreen request={analyzeReq} />}
                  {view === 'portfolio' && <PortfolioScreen />}
                  {view === 'earnings' && <EarningsScreen />}
                  {view === 'lab' && user?.is_admin && <LabScreen />}
                  {view === 'settings' && <SettingsScreen />}
                  {view === 'admin' && user?.is_admin && <AdminScreen />}
                </Suspense>
              </main>
            </div>
            {/* Mounted only while open, so each opening starts fresh. */}
            <CommandPalette
              key={palette ? 'open' : 'closed'}
              open={palette}
              onClose={() => setPalette(false)}
              go={go}
              analyze={chrome.analyze}
            />
          </div>
        </ChatsProvider>

        <PlusSheet open={plusOpen} onClose={() => setPlusOpen(false)} />
        <WelcomeSheet />
        <GiftSheet />
        {whatsNew && (
          <Suspense fallback={null}>
            <WhatsNewSheet open={whatsNew} onClose={() => setWhatsNew(false)} />
          </Suspense>
        )}
      </ToastProvider>
      <ReportSheet open={report.open} transcript={report.transcript} onClose={() => setReport({ open: false })} />
    </ChromeContext.Provider>
  )
}

function Sidebar({
  view,
  go,
  unseen,
  onClose,
  onSearch,
}: {
  view: View
  go: (v: View) => void
  unseen: boolean
  onClose: () => void
  onSearch: () => void
}) {
  const { user, isGuest, signOut } = useSession()
  // Out of guest mode onto the auth screen, opened on the form they picked.
  function leaveGuest(mode: 'signup' | 'login') {
    try {
      sessionStorage.setItem('paula-auth-mode', mode)
    } catch {
      /* lands on sign-in */
    }
    signOut()
  }
  const { chats, active, select, create, remove, restore, scan } = useChats()
  const toast = useToast()
  const { openPlus, openReport, openWhatsNew } = useChrome()

  function newChat() {
    if (!create()) {
      openPlus()
      return
    }
    go('chat')
  }

  const name = user?.username ?? 'Guest'

  return (
    <aside className="sidebar" aria-label="Navigation">
      <div className="sidebar-brand">
        <span className="brand-mark">P</span>
        <span className="brand-name">Paula</span>
        <button className="btn btn-ghost btn-icon btn-sm sidebar-close" onClick={onClose} aria-label="Close menu">
          <X size={16} />
        </button>
      </div>

      <button className="btn btn-secondary sidebar-new" onClick={newChat}>
        <SquarePen size={15} />
        New chat
      </button>
      <button className="sidebar-search" onClick={onSearch}>
        <Search size={14} />
        <span>Search…</span>
        <kbd className="kbd">{isMac ? '⌘' : 'Ctrl'}</kbd>
        <kbd className="kbd">K</kbd>
      </button>

      <nav className="nav">
        {[...PRIMARY, ...(user?.is_admin ? LAB_NAV : [])].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={'nav-item' + (view === id ? ' nav-item-on' : '')}
            onClick={() => go(id)}
            aria-current={view === id ? 'page' : undefined}
          >
            <Icon size={16} strokeWidth={1.8} />
            {label}
          </button>
        ))}
      </nav>

      <div className="sidebar-section">
        <span className="sidebar-label">Recent chats</span>
        <ul className="recent">
          {chats.length === 0 && <li className="recent-empty">Your conversations will show up here.</li>}
          {chats.map((c) => (
            <li key={c.id} className={'recent-item' + (view === 'chat' && c.id === active?.id ? ' recent-item-on' : '')}>
              <button
                className="recent-title"
                title={c.title}
                onClick={() => {
                  select(c.id)
                  go('chat')
                }}
              >
                {scan?.chatId === c.id && <span className="recent-live" aria-label="Scan running" />}
                {c.title}
              </button>
              <button
                className="recent-del"
                onClick={() => {
                  const index = chats.findIndex((x) => x.id === c.id)
                  remove(c.id)
                  toast.show(`Deleted “${c.title}”`, { label: 'Undo', run: () => restore(c, index) })
                }}
                aria-label={`Delete ${c.title}`}
              >
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="sidebar-foot">
        {isGuest ? (
          // Logged-out sidebar, as ChatGPT does it: why sign up, and both doors.
          <div className="guest-promo">
            <strong>Save your chats and get the calendar</strong>
            <small>A free account keeps your history, unlocks earnings and research, and syncs across devices.</small>
            <div className="guest-promo-actions">
              <button className="btn btn-primary btn-sm" onClick={() => leaveGuest('signup')}>
                Sign up free
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => leaveGuest('login')}>
                Log in
              </button>
            </div>
          </div>
        ) : !user?.plus && !user?.is_admin && (
          <button className="plus-promo" onClick={openPlus}>
            <Sparkles size={15} />
            <span>
              <strong>Paula Plus</strong>
              <small>Unlimited messages and the full signal</small>
            </span>
          </button>
        )}

        <nav className="nav">
          <button
            className={'nav-item' + (view === 'settings' ? ' nav-item-on' : '')}
            onClick={() => go('settings')}
          >
            <Settings size={16} strokeWidth={1.8} />
            Settings
          </button>
          {user?.is_admin && (
            <button className={'nav-item' + (view === 'admin' ? ' nav-item-on' : '')} onClick={() => go('admin')}>
              <ShieldCheck size={16} strokeWidth={1.8} />
              Admin
            </button>
          )}
          <button className="nav-item" onClick={() => openReport()}>
            <Bug size={16} strokeWidth={1.8} />
            Report a problem
          </button>
          <button className="nav-item" onClick={openWhatsNew}>
            <Gift size={16} strokeWidth={1.8} />
            What’s new
            {unseen ? <span className="nav-new">New</span> : <span className="nav-version">v{VERSION}</span>}
          </button>
        </nav>

        <div className="sidebar-theme">
          <span className="sidebar-label">Theme</span>
          <ThemeSwitch />
        </div>

        <div className="account">
          <span className="account-avatar">{name.slice(0, 1).toUpperCase()}</span>
          <span className="account-text">
            <span className="account-name">
              {name}
              {user?.plus && <span className="badge badge-green">Plus</span>}
            </span>
            <span className="account-email">{user?.email ?? 'Not signed in'}</span>
          </span>
          <button
            className="btn btn-ghost btn-icon btn-sm"
            onClick={signOut}
            aria-label={isGuest ? 'Exit guest mode' : 'Sign out'}
            title={isGuest ? 'Exit guest mode' : 'Sign out'}
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  )
}
