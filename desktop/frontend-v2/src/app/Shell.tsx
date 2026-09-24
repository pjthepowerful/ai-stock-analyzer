import {
  Bug,
  CalendarDays,
  ChartCandlestick,
  LogOut,
  Menu,
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
import { lazy, Suspense, useMemo, useState } from 'react'
import { ChatScreen } from '../features/chat/ChatScreen'
import { ReportSheet } from '../features/feedback/ReportSheet'
import { PlusSheet } from '../features/plus/PlusSheet'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import type { ChatMessage } from '../lib/api'
import { useSession } from '../lib/auth'
import { ChatsProvider, useChats } from '../lib/chats'
import { ChromeContext, useChrome, type Chrome } from '../lib/chrome'
import './shell.css'

// Chat is the landing screen; the chart-heavy and owner-only screens load on
// first visit so they don't weigh down the first paint.
const AdminScreen = lazy(() => import('../features/admin/AdminScreen').then((m) => ({ default: m.AdminScreen })))
const AnalyzeScreen = lazy(() => import('../features/analyze/AnalyzeScreen').then((m) => ({ default: m.AnalyzeScreen })))
const EarningsScreen = lazy(() => import('../features/earnings/EarningsScreen').then((m) => ({ default: m.EarningsScreen })))
const PortfolioScreen = lazy(() =>
  import('../features/portfolio/PortfolioScreen').then((m) => ({ default: m.PortfolioScreen })),
)

type View = 'chat' | 'analyze' | 'portfolio' | 'earnings' | 'settings' | 'admin'

const PRIMARY: { id: View; label: string; icon: LucideIcon }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'analyze', label: 'Analyze', icon: ChartCandlestick },
  { id: 'portfolio', label: 'Portfolio', icon: Wallet },
  { id: 'earnings', label: 'Earnings', icon: CalendarDays },
]

const TITLES: Record<View, string> = {
  chat: 'Chat',
  analyze: 'Analyze',
  portfolio: 'Portfolio',
  earnings: 'Earnings',
  settings: 'Settings',
  admin: 'Admin',
}

export function Shell() {
  const { user } = useSession()
  const [view, setView] = useState<View>('chat')
  const [drawer, setDrawer] = useState(false)
  const [plusOpen, setPlusOpen] = useState(false)
  const [report, setReport] = useState<{ open: boolean; transcript?: ChatMessage[] }>({ open: false })

  const chrome = useMemo<Chrome>(
    () => ({
      openPlus: () => setPlusOpen(true),
      openReport: (transcript) => setReport({ open: true, transcript }),
    }),
    [],
  )

  function go(v: View) {
    setView(v)
    setDrawer(false)
  }

  return (
    <ChromeContext.Provider value={chrome}>
      {/* Keyed per account so signing in/out swaps to that account's chats. */}
      <ChatsProvider key={user ? `u${user.id}` : 'guest'}>
        <div className={'app' + (drawer ? ' app-drawer-open' : '')}>
          <Sidebar view={view} go={go} onClose={() => setDrawer(false)} />
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
                {view === 'chat' && <ChatScreen onNavigateAnalyze={() => go('analyze')} />}
                {view === 'analyze' && <AnalyzeScreen />}
                {view === 'portfolio' && <PortfolioScreen />}
                {view === 'earnings' && <EarningsScreen />}
                {view === 'settings' && <SettingsScreen />}
                {view === 'admin' && user?.is_admin && <AdminScreen />}
              </Suspense>
            </main>
          </div>
        </div>
      </ChatsProvider>

      <PlusSheet open={plusOpen} onClose={() => setPlusOpen(false)} />
      <ReportSheet open={report.open} transcript={report.transcript} onClose={() => setReport({ open: false })} />
    </ChromeContext.Provider>
  )
}

function Sidebar({ view, go, onClose }: { view: View; go: (v: View) => void; onClose: () => void }) {
  const { user, isGuest, signOut } = useSession()
  const { chats, active, select, create, remove, scan } = useChats()
  const { openPlus, openReport } = useChrome()
  const [confirming, setConfirming] = useState<string | null>(null)

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

      <nav className="nav">
        {PRIMARY.map(({ id, label, icon: Icon }) => (
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
              {confirming === c.id ? (
                <div className="recent-confirm">
                  <span>Delete chat?</span>
                  <button
                    className="recent-yes"
                    onClick={() => {
                      remove(c.id)
                      setConfirming(null)
                    }}
                  >
                    Delete
                  </button>
                  <button className="recent-no" onClick={() => setConfirming(null)}>
                    Keep
                  </button>
                </div>
              ) : (
                <>
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
                  <button className="recent-del" onClick={() => setConfirming(c.id)} aria-label={`Delete ${c.title}`}>
                    <Trash2 size={13} />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="sidebar-foot">
        {!user?.plus && !user?.is_admin && (
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
        </nav>

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
