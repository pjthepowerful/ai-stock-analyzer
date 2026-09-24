import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { AnalyzeData } from '../components/SignalCard'
import { api } from './api'
import { useSession } from './auth'
import { useWebSocket } from './ws'

// Same shape the original app stores in synced_chats, so chats move freely
// between the two apps. `meta` is v2-only and ignored by the original.
export interface StoredMessage {
  role: 'user' | 'assistant'
  content: string
  time?: string
  meta?: { taste?: boolean; limitReached?: boolean; card?: AnalyzeData }
}

export interface Chat {
  id: string
  title: string
  created: string
  messages: StoredMessage[]
}

interface SyncResponse {
  ok: boolean
  chats?: Chat[]
  updated_at: number
  applied?: boolean
}

export interface ScanState {
  chatId: string
  scanId: string
  pct: number
  label: string
}

interface Chats {
  scan: ScanState | null
  /** Marks a server-side scan as running on behalf of this chat. */
  startScan: (chatId: string, scanId: string) => void
  chats: Chat[]
  active: Chat | null
  select: (id: string) => void
  /** Returns false when the free-tier limit blocks a new chat. */
  create: () => boolean
  remove: (id: string) => void
  /** Put a just-deleted chat back where it was (Undo). */
  restore: (chat: Chat, index: number) => void
  append: (chatId: string, msg: StoredMessage) => void
  rename: (chatId: string, title: string) => void
  /** Makes sure there's an active chat to write into and returns its id. */
  ensureActive: () => string
}

const ChatsContext = createContext<Chats | null>(null)

const FREE_CHAT_LIMIT = 1
// Must match the keys ChatsProvider derives for owner 'guest'.
const GUEST_KEY = 'paula-v2-chats-guest'
const GUEST_TS_KEY = 'paula-v2-chats-ts-guest'
const NEW_TITLE = 'New chat'

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function blankChat(): Chat {
  return { id: newId(), title: NEW_TITLE, created: new Date().toISOString(), messages: [] }
}

function readJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* storage full or blocked — the server copy is still authoritative */
  }
}

export function ChatsProvider({ children }: { children: ReactNode }) {
  const { user, isGuest } = useSession()
  const owner = user ? String(user.id) : 'guest'
  const keys = useMemo(
    () => ({ chats: `paula-v2-chats-${owner}`, ts: `paula-v2-chats-ts-${owner}`, active: `paula-v2-chat-${owner}` }),
    [owner],
  )

  const [chats, setChats] = useState<Chat[]>(() => readJSON(keys.chats, []))
  const [activeId, setActiveId] = useState<string | null>(() => localStorage.getItem(keys.active))
  const chatsRef = useRef(chats)
  // Pushes stay off until the first pull has reconciled; otherwise a fresh
  // device's empty list would overwrite real chats on the server.
  const syncReady = useRef(isGuest)
  const pushTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const canSync = !!user && !isGuest

  const adopt = useCallback(
    (next: Chat[], ts: number) => {
      chatsRef.current = next
      setChats(next)
      write(keys.chats, JSON.stringify(next))
      write(keys.ts, String(ts))
    },
    [keys],
  )

  const push = useCallback(() => {
    if (!canSync || !syncReady.current) return
    if (pushTimer.current) clearTimeout(pushTimer.current)
    pushTimer.current = setTimeout(() => {
      const updated_at = Number(localStorage.getItem(keys.ts)) || Date.now()
      api
        .put<SyncResponse>('/api/chats/sync', { chats: chatsRef.current, updated_at })
        .then((res) => {
          if (res.applied === false && res.chats) adopt(res.chats, res.updated_at)
        })
        .catch(() => {
          /* offline — the next edit retries with a newer timestamp */
        })
    }, 800)
  }, [adopt, canSync, keys])

  const commit = useCallback(
    (update: (prev: Chat[]) => Chat[]) => {
      const next = update(chatsRef.current)
      chatsRef.current = next
      setChats(next)
      write(keys.chats, JSON.stringify(next))
      write(keys.ts, String(Date.now()))
      push()
    },
    [keys, push],
  )

  const select = useCallback(
    (id: string) => {
      setActiveId(id)
      write(keys.active, id)
    },
    [keys],
  )

  // Initial pull: last-write-wins against whatever this device cached.
  useEffect(() => {
    if (!canSync) return
    let cancelled = false
    api
      .get<SyncResponse>('/api/chats/sync')
      .then((res) => {
        if (cancelled) return
        const localTs = Number(localStorage.getItem(keys.ts)) || 0
        if ((res.updated_at || 0) > localTs && res.chats) adopt(res.chats, res.updated_at)
        syncReady.current = true

        // Chats made as a guest on this device follow you into the account
        // you sign in to (once — they're removed from guest storage after).
        const guest = readJSON<Chat[]>(GUEST_KEY, []).filter((c) => c.messages.length > 0)
        if (guest.length) {
          const have = new Set(chatsRef.current.map((c) => c.id))
          const fresh = guest.filter((c) => !have.has(c.id))
          try {
            localStorage.removeItem(GUEST_KEY)
            localStorage.removeItem(GUEST_TS_KEY)
          } catch {
            /* ignore */
          }
          if (fresh.length) {
            commit((prev) => [...fresh, ...prev])
            select(fresh[0].id)
            return
          }
        }
        if (localTs > (res.updated_at || 0)) push()
      })
      .catch(() => {
        if (!cancelled) syncReady.current = true
      })
    return () => {
      cancelled = true
    }
  }, [adopt, canSync, commit, keys, push, select])

  const active = chats.find((c) => c.id === activeId) ?? chats[0] ?? null

  const create = useCallback(() => {
    const current = chatsRef.current
    // An untouched blank chat is reused rather than stacking empties.
    const blank = current.find((c) => c.messages.length === 0)
    if (blank) {
      select(blank.id)
      return true
    }
    if (!user?.plus && !user?.is_admin && current.length >= FREE_CHAT_LIMIT) return false
    const chat = blankChat()
    commit((prev) => [chat, ...prev])
    select(chat.id)
    return true
  }, [commit, select, user])

  const remove = useCallback(
    (id: string) => {
      commit((prev) => prev.filter((c) => c.id !== id))
      if (activeId === id) {
        const next = chatsRef.current[0]
        if (next) select(next.id)
      }
    },
    [activeId, commit, select],
  )

  const restore = useCallback(
    (chat: Chat, index: number) => {
      commit((prev) => {
        if (prev.some((c) => c.id === chat.id)) return prev
        const next = [...prev]
        next.splice(Math.min(index, next.length), 0, chat)
        return next
      })
      select(chat.id)
    },
    [commit, select],
  )

  const append = useCallback(
    (chatId: string, msg: StoredMessage) => {
      const stamped = { ...msg, time: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) }
      commit((prev) => prev.map((c) => (c.id === chatId ? { ...c, messages: [...c.messages, stamped] } : c)))
    },
    [commit],
  )

  const rename = useCallback(
    (chatId: string, title: string) => commit((prev) => prev.map((c) => (c.id === chatId ? { ...c, title } : c))),
    [commit],
  )

  const ensureActive = useCallback(() => {
    if (active) return active.id
    const chat = blankChat()
    commit((prev) => [chat, ...prev])
    select(chat.id)
    return chat.id
  }, [active, commit, select])

  // Scans run on the server and report over the websocket. Tracking them
  // here (not in ChatScreen) means the result still lands in the chat that
  // started it after you switch chats or tabs.
  const [scan, setScan] = useState<ScanState | null>(null)
  const scanRef = useRef<{ chatId: string; scanId: string } | null>(null)
  const startScan = useCallback((chatId: string, scanId: string) => {
    scanRef.current = { chatId, scanId }
    setScan({ chatId, scanId, pct: 0, label: 'Starting…' })
  }, [])

  useWebSocket((e) => {
    // Scan events are broadcast to every client; only act on our own scan.
    const mine = scanRef.current
    if (!mine || e.data.scan_id !== mine.scanId) return
    if (e.event === 'scan_progress') {
      setScan((s) => (s ? { ...s, pct: Number(e.data.pct ?? 0), label: String(e.data.label ?? '') } : s))
    }
    if (e.event === 'scan_result') {
      scanRef.current = null
      setScan(null)
      append(mine.chatId, { role: 'assistant', content: String(e.data.message ?? '') })
    }
  })

  const value = useMemo(
    () => ({ scan, startScan, chats, active, select, create, remove, restore, append, rename, ensureActive }),
    [scan, startScan, chats, active, select, create, remove, restore, append, rename, ensureActive],
  )

  return <ChatsContext.Provider value={value}>{children}</ChatsContext.Provider>
}

export function useChats() {
  const ctx = useContext(ChatsContext)
  if (!ctx) throw new Error('useChats must be used within ChatsProvider')
  return ctx
}

export { NEW_TITLE }
