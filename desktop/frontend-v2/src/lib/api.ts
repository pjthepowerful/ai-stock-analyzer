import type { Signal } from '../components/SignalCard'

// Set VITE_API_URL when hosting (e.g. the Railway backend); local dev uses :4141.
export const API_BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:4141').replace(/\/+$/, '')

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function getToken(): string | null {
  return localStorage.getItem('paula-v2-token')
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem('paula-v2-token', token)
  else localStorage.removeItem('paula-v2-token')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  const body = await res.json().catch(() => ({}))

  if (!res.ok) {
    // Real status codes now (see backend-v2 plan note) — a 401/422/etc IS the
    // error signal, not a 200 with {ok:false} to check by hand everywhere.
    const detail = body?.detail ?? body?.error
    // FastAPI validation errors arrive as a list of {loc, msg}; show the first.
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail) && typeof detail[0]?.msg === 'string'
          ? detail[0].msg
          : res.statusText || 'Request failed'
    throw new ApiError(res.status, message)
  }
  return body as T
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: data ? JSON.stringify(data) : undefined }),
  put: <T>(path: string, data: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(data) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

export interface AuthUser {
  id: number
  username: string
  email: string
  plus?: boolean
  is_admin?: boolean
  can_autopilot?: boolean
  /** Note from the team when Plus was gifted (from /api/auth/me). */
  gift_msg?: string
}

export interface MeResponse {
  ok: boolean
  user: AuthUser
  gift_msg: string
  messages_today: number
}

export interface AuthResult {
  ok: boolean
  token?: string
  user?: AuthUser
  needs_2fa?: boolean
  needs_verification?: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** An order Paula understood from chat. Nothing is placed until the user
 *  confirms it (POST /api/trade/execute). */
export interface TradeIntent {
  action: 'buy' | 'sell' | 'short' | 'cover' | 'cancel_orders' | 'close_all'
  ticker?: string
  qty?: number | null
  notional?: number | null
  smart?: boolean
  sell_all?: boolean
  cover_all?: boolean
}

export interface ChatResponse {
  ok: boolean
  type: string
  message: string
  trade?: TradeIntent
  ticker?: string | null
  tickers?: string[]
  taste?: boolean
  plus_upsell?: boolean
  limit_reached?: boolean
  scan_id?: string
  trade_signal?: Signal | null
  quote?: { ticker: string; name?: string; price: number; change: number; change_pct: number } | null
}
