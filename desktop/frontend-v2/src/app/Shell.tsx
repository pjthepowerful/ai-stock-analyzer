import { useMemo, useState } from 'react'
import { AdminScreen } from '../features/admin/AdminScreen'
import { AnalyzeScreen } from '../features/analyze/AnalyzeScreen'
import { ChatScreen } from '../features/chat/ChatScreen'
import { ReportSheet } from '../features/feedback/ReportSheet'
import { PlusSheet } from '../features/plus/PlusSheet'
import { PortfolioScreen } from '../features/portfolio/PortfolioScreen'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import type { ChatMessage } from '../lib/api'
import { useSession } from '../lib/auth'
import { ChromeContext, type Chrome } from '../lib/chrome'
import './shell.css'

type View = 'chat' | 'analyze' | 'portfolio' | 'settings' | 'admin'

const TABS: { id: View; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'analyze', label: 'Analyze' },
  { id: 'portfolio', label: 'Portfolio' },
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
          {view === 'chat' && <ChatScreen onNavigateAnalyze={() => setView('analyze')} />}
          {view === 'analyze' && <AnalyzeScreen />}
          {view === 'portfolio' && <PortfolioScreen />}
          {view === 'settings' && <SettingsScreen />}
          {view === 'admin' && user?.is_admin && <AdminScreen />}
        </main>
      </div>

      <PlusSheet open={plusOpen} onClose={() => setPlusOpen(false)} />
      <ReportSheet
        open={report.open}
        transcript={report.transcript}
        onClose={() => setReport({ open: false })}
      />
    </ChromeContext.Provider>
  )
}
