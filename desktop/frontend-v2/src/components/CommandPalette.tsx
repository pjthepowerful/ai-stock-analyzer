import {
  Bug,
  CalendarDays,
  ChartCandlestick,
  CornerDownLeft,
  MessageSquare,
  Monitor,
  Moon,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  SquarePen,
  Sun,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSession } from '../lib/auth'
import { useChats } from '../lib/chats'
import { useChrome } from '../lib/chrome'
import { setThemePref } from '../lib/theme'
import { searchTickers } from '../lib/tickers'
import './CommandPalette.css'

export type View = 'chat' | 'analyze' | 'portfolio' | 'earnings' | 'settings' | 'admin'

interface Item {
  id: string
  group: string
  label: string
  hint?: string
  icon: LucideIcon
  keywords?: string
  run: () => void
}

interface Props {
  open: boolean
  onClose: () => void
  go: (v: View) => void
  analyze: (ticker: string) => void
}

/** ⌘K menu: jump anywhere, run common actions, analyze a ticker by name. */
export function CommandPalette({ open, onClose, go, analyze }: Props) {
  const { user } = useSession()
  const { chats, select, create } = useChats()
  const { openPlus, openReport } = useChrome()
  const [query, setQuery] = useState('')
  const [hi, setHi] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)


  const items = useMemo<Item[]>(() => {
    const base: Item[] = [
      { id: 'go-chat', group: 'Go to', label: 'Chat', icon: MessageSquare, run: () => go('chat') },
      { id: 'go-analyze', group: 'Go to', label: 'Analyze', icon: ChartCandlestick, run: () => go('analyze') },
      { id: 'go-portfolio', group: 'Go to', label: 'Portfolio', icon: Wallet, keywords: 'equity positions', run: () => go('portfolio') },
      { id: 'go-earnings', group: 'Go to', label: 'Earnings', icon: CalendarDays, keywords: 'calendar ideas', run: () => go('earnings') },
      { id: 'go-settings', group: 'Go to', label: 'Settings', icon: Settings, keywords: 'account alpaca', run: () => go('settings') },
      ...(user?.is_admin
        ? [{ id: 'go-admin', group: 'Go to', label: 'Admin', icon: ShieldCheck, run: () => go('admin') }]
        : []),
      {
        id: 'new-chat',
        group: 'Actions',
        label: 'New chat',
        icon: SquarePen,
        run: () => (create() ? go('chat') : openPlus()),
      },
      { id: 'report', group: 'Actions', label: 'Report a problem', icon: Bug, keywords: 'bug feedback', run: () => openReport() },
      ...(!user?.plus && !user?.is_admin
        ? [{ id: 'plus', group: 'Actions', label: 'Get Paula Plus', icon: Sparkles, keywords: 'upgrade', run: openPlus }]
        : []),
      { id: 'theme-light', group: 'Theme', label: 'Light theme', icon: Sun, run: () => setThemePref('light') },
      { id: 'theme-dark', group: 'Theme', label: 'Dark theme', icon: Moon, run: () => setThemePref('dark') },
      { id: 'theme-system', group: 'Theme', label: 'Match system theme', icon: Monitor, keywords: 'auto', run: () => setThemePref('system') },
    ]
    const recent: Item[] = chats
      .filter((c) => c.messages.length > 0)
      .slice(0, 6)
      .map((c) => ({
        id: `chat-${c.id}`,
        group: 'Recent chats',
        label: c.title,
        icon: MessageSquare,
        run: () => {
          select(c.id)
          go('chat')
        },
      }))
    return [...base, ...recent]
  }, [chats, create, go, openPlus, openReport, select, user])

  const q = query.trim().toLowerCase()
  const filtered = q
    ? items.filter((i) => `${i.label} ${i.group} ${i.keywords ?? ''}`.toLowerCase().includes(q))
    : items
  const tickerItems: Item[] = searchTickers(query, 5).map(([t, n]) => ({
    id: `tk-${t}`,
    group: 'Analyze',
    label: `${t}`,
    hint: n,
    icon: ChartCandlestick,
    run: () => analyze(t),
  }))
  // A bare symbol that isn't in the list can still be analyzed.
  const sym = query.trim().toUpperCase()
  if (/^[A-Z.-]{1,6}$/.test(sym) && !tickerItems.some((t) => t.label === sym)) {
    tickerItems.push({
      id: `tk-raw-${sym}`,
      group: 'Analyze',
      label: sym,
      hint: 'Analyze this symbol',
      icon: ChartCandlestick,
      run: () => analyze(sym),
    })
  }
  const all = q ? [...tickerItems, ...filtered] : filtered

  // Keep the highlighted row in view while arrowing through the list.
  useEffect(() => {
    listRef.current?.querySelector('[data-hi="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [hi])

  if (!open) return null

  function runItem(item: Item | undefined) {
    if (!item) return
    onClose()
    item.run()
  }

  let lastGroup = ''
  return (
    <div className="cmdk-scrim" onMouseDown={onClose}>
      <div
        className="cmdk"
        role="dialog"
        aria-modal="true"
        aria-label="Command menu"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="cmdk-search">
          <Search size={16} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setHi(0)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setHi((h) => Math.min(h + 1, all.length - 1))
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                setHi((h) => Math.max(h - 1, 0))
              } else if (e.key === 'Enter') {
                e.preventDefault()
                runItem(all[hi])
              } else if (e.key === 'Escape') {
                onClose()
              }
            }}
            autoFocus
            placeholder="Search pages, actions, or a ticker…"
            aria-label="Search commands"
            role="combobox"
            aria-expanded="true"
            aria-controls="cmdk-list"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="kbd">esc</kbd>
        </div>

        <div className="cmdk-list" id="cmdk-list" role="listbox" ref={listRef}>
          {all.length === 0 && <p className="cmdk-empty">No results for “{query}”.</p>}
          {all.map((item, i) => {
            const header = item.group !== lastGroup ? item.group : null
            lastGroup = item.group
            const Icon = item.icon
            return (
              <div key={item.id}>
                {header && <div className="cmdk-group">{header}</div>}
                <button
                  role="option"
                  aria-selected={i === hi}
                  data-hi={i === hi}
                  className={'cmdk-item' + (i === hi ? ' cmdk-item-on' : '')}
                  onMouseMove={() => setHi(i)}
                  onClick={() => runItem(item)}
                >
                  <Icon size={15} strokeWidth={1.8} />
                  <span className="cmdk-label">{item.label}</span>
                  <span className="cmdk-hint">{item.hint}</span>
                  <CornerDownLeft size={13} className="cmdk-enter" aria-hidden />
                </button>
              </div>
            )
          })}
        </div>

        <div className="cmdk-foot">
          <span>
            <kbd className="kbd">↑</kbd>
            <kbd className="kbd">↓</kbd> to move
          </span>
          <span>
            <kbd className="kbd">↵</kbd> to open
          </span>
        </div>
      </div>
    </div>
  )
}
