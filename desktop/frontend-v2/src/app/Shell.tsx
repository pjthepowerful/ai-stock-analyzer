import { lazy, Suspense, useMemo, useState } from 'react'
import { ChatScreen } from '../features/chat/ChatScreen'
import { ReportSheet } from '../features/feedback/ReportSheet'
import { PlusSheet } from '../features/plus/PlusSheet'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import type { ChatMessage } from '../lib/api'
import { useSession } from '../lib/auth'
import { ChatsProvider } from '../lib/chats'
import { ChromeContext, type Chrome } from '../lib/chrome'
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

const TABS: { id: View; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'analyze', label: 'Analyze' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'earnings', label: 'Earnings' },
  { id: 'settings', label: 'Settings' },
]

export function Shell() {
  const { user, isGuest, signOut } = useSession()
  const [view, setView] = useState<View>('chat')
  const [plusOpen, setPlusOpen] = useState(false)
  const [report, setReport] = useState<{ open: boolean; transcript?: ChatMessage[] }>({ open: false })

  const chrome = useMemo<Chrome>(
    () => ({
      openPlus: () => setPlusOpen(true),
      openReport: (transcript) => setReport({ open: true, transcript }),
    }),
    [],
  )

  const tabs = user?.is_admin ? [...TABS, { id: 'admin' as View, label: 'Admin' }] : TABS

  return (
    <ChromeContext.Provider value={chrome}>
      {/* Keyed per account so signing in/out swaps to that account's chats. */}
      <ChatsProvider key={user ? `u${user.id}` : 'guest'}>
        <div className="shell">
          <header className="shell-header">
            <span className="shell-logo">P</span>
            <span className="shell-title">Paula</span>
            <span className="shell-badge">preview</span>

            <nav className="shell-tabs">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  className={'shell-tab' + (view === t.id ? ' shell-tab-on' : '')}
                  onClick={() => setView(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </nav>

            <div className="shell-header-spacer" />
            {!user?.plus && !user?.is_admin && (
              <button className="shell-upgrade" onClick={chrome.openPlus}>
                Get Plus
              </button>
            )}
            <button className="shell-quiet" onClick={() => chrome.openReport()}>
              Report a problem
            </button>
            <span className="shell-user">
              {user?.username ?? 'Guest'}
              {user?.plus && <span className="shell-plus-mark">PLUS</span>}
            </span>
            <button className="shell-quiet" onClick={signOut}>
              {isGuest ? 'Exit guest' : 'Sign out'}
            </button>
          </header>

          <main className="shell-content">
            <Suspense fallback={null}>
            {view === 'chat' && <ChatScreen onNavigateAnalyze={() => setView('analyze')} />}
            {view === 'analyze' && <AnalyzeScreen />}
            {view === 'portfolio' && <PortfolioScreen />}
            {view === 'earnings' && <EarningsScreen />}
            {view === 'settings' && <SettingsScreen />}
            {view === 'admin' && user?.is_admin && <AdminScreen />}
            </Suspense>
          </main>
        </div>
      </ChatsProvider>

      <PlusSheet open={plusOpen} onClose={() => setPlusOpen(false)} />
      <ReportSheet
        open={report.open}
        transcript={report.transcript}
        onClose={() => setReport({ open: false })}
      />
    </ChromeContext.Provider>
  )
}
