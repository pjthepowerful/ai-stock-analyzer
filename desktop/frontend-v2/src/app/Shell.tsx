import { useState } from 'react'
import { AnalyzeScreen } from '../features/analyze/AnalyzeScreen'
import { ChatScreen } from '../features/chat/ChatScreen'
import { PortfolioScreen } from '../features/portfolio/PortfolioScreen'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import { useSession } from '../lib/auth'
import './shell.css'

type View = 'chat' | 'analyze' | 'portfolio' | 'settings'

const TABS: { id: View; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'analyze', label: 'Analyze' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'settings', label: 'Settings' },
]

export function Shell() {
  const { user, isGuest, signOut } = useSession()
  const [view, setView] = useState<View>('chat')

  return (
    <div className="shell">
      <header className="shell-header">
        <span className="shell-logo">P</span>
        <span className="shell-title">Paula</span>
        <span className="shell-badge">preview</span>

        <nav className="shell-tabs">
          {TABS.map((t) => (
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
        <span className="shell-user">{user?.username ?? 'Guest'}</span>
        <button className="shell-signout" onClick={signOut}>
          {isGuest ? 'Exit guest' : 'Sign out'}
        </button>
      </header>

      <main className="shell-content">
        {view === 'chat' && <ChatScreen onNavigateAnalyze={() => setView('analyze')} />}
        {view === 'analyze' && <AnalyzeScreen />}
        {view === 'portfolio' && <PortfolioScreen />}
        {view === 'settings' && <SettingsScreen />}
      </main>
    </div>
  )
}
