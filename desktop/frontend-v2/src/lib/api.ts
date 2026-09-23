const API_BASE = 'http://127.0.0.1:4141'

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
    const message = body?.detail || body?.error || res.statusText
    throw new ApiError(res.status, typeof message === 'string' ? message : 'Request failed')
  }
  return body as T
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: data ? JSON.stringify(data) : undefined }),
}

export interface AuthUser {
  id: number
  username: string
  email: string
  plus?: boolean
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

export interface ChatResponse {
  ok: boolean
  type: string
  message: string
  ticker?: string | null
  tickers?: string[]
  taste?: boolean
  plus_upsell?: boolean
  limit_reached?: boolean
}
