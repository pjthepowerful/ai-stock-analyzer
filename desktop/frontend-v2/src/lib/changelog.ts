// Paula's version and release notes. Bump VERSION on every shipped change
// (patch = fix, minor = feature, major = big release) and add an entry here.
// Entries with a `demo` get a Before / After button in What's new.

export const VERSION = '5.0.0'
export const VERSION_DATE = 'September 23, 2026'

export interface Demo {
  before: string
  after: string
  caption: string
}

export interface Highlight {
  title: string
  desc: string
  demo?: Demo
}

export interface Release {
  v: string
  d: string
  title?: string
  highlights?: Highlight[]
  changes: string[]
}

export const RELEASES: Release[] = [
  {
    v: '5.0.0',
    d: VERSION_DATE,
    title: 'A whole new Paula',
    highlights: [
      {
        title: 'Rebuilt from the ground up',
        desc: 'A new app frame — sidebar, cards, one type family — so every screen feels like the same product. Black by default, with Light and System in one click.',
        demo: {
          before: '/whatsnew/chat-before.jpg',
          after: '/whatsnew/chat-after.jpg',
          caption: 'Same question, same engine — the new chat, sidebar and market strip.',
        },
      },
      {
        title: 'New sign-in',
        desc: 'A cleaner sign-in with a live preview of what Paula does, proper autofill and a show-password toggle.',
        demo: {
          before: '/whatsnew/signin-before.jpg',
          after: '/whatsnew/signin-after.jpg',
          caption: 'Sign-in, before and after.',
        },
      },
      {
        title: 'Find anything with ⌘K',
        desc: 'Jump to any page, start a chat, switch theme or analyze a ticker by company name — press ⌘K (Ctrl+K) or use Search in the sidebar.',
      },
      {
        title: 'Trending on Paula',
        desc: 'Popular tickers now come from what people actually look up this week, not a fixed list.',
      },
    ],
    changes: [
      'Autopilot controls in Settings: start/stop, pick a strategy, and see recent activity. It keeps running with the app closed and comes back on its own after a restart.',
      'Orders from chat (“buy 5 AAPL”, “close all”) show a confirm card first — nothing is sent to your broker until you press Confirm.',
      'Saved chats that sync across devices, with one-click delete and Undo.',
      'Analyze: autocomplete by symbol or company, recent tickers, the signal card beside the chart, and an earnings / fundamentals / news panel.',
      'Portfolio: equity curve with ranges, activity by week or month, positions table, S&P comparison and day-trade headroom.',
      'Earnings tab: month calendar with Paula’s read on every report, plus Ideas — likely beats and post-earnings drift.',
      'The typing greeting is back, with a snapshot of your account underneath.',
      'Thank-you screens after upgrading to Plus and after sending a report, and a welcome for new accounts.',
      'Tickers are clickable everywhere — positions, calendar, ideas and the market strip open straight in Analyze.',
      'Much faster: rankings 60–78s → 10–15s, repeat stock lookups instant, screens preload in the background.',
      'Fixes: per-user broker keys were ignored inside chat, scan results could reach the wrong chat, guests shared one history and had no message limit, a backend restart signed you out, saving settings wiped other settings, and the autopilot config was rewritten on every read.',
    ],
  },
]
