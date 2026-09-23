import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, setToken, type AuthResult, type AuthUser, type MeResponse } from './api'

interface Session {
  user: AuthUser | null
  isGuest: boolean
  loading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (username: string, email: string, password: string) => Promise<void>
  continueAsGuest: () => void
  signOut: () => void
  /** Re-reads /me — call after anything that changes plan or role. */
  refresh: () => Promise<void>
}

const SessionContext = createContext<Session | null>(null)

const GUEST_KEY = 'paula-v2-guest'

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isGuest, setIsGuest] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('paula-v2-token')
    if (!token) {
      if (localStorage.getItem(GUEST_KEY) === '1') setIsGuest(true)
      setLoading(false)
      return
    }
    api
      .get<MeResponse>('/api/auth/me')
      .then((res) => setUser(res.user))
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  async function refresh() {
    try {
      const res = await api.get<MeResponse>('/api/auth/me')
      setUser(res.user)
    } catch {
      /* keep the current user; a transient failure shouldn't sign anyone out */
    }
  }

  async function login(email: string, password: string) {
    setError(null)
    try {
      const res = await api.post<AuthResult>('/api/auth/login', { email, password })
      if (res.token) {
        setToken(res.token)
        setUser(res.user ?? null)
        setIsGuest(false)
        localStorage.removeItem(GUEST_KEY)
        await refresh()
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not sign in')
      throw e
    }
  }

  async function signup(username: string, email: string, password: string) {
    setError(null)
    try {
      const res = await api.post<AuthResult>('/api/auth/signup', { username, email, password })
      if (res.token) {
        setToken(res.token)
        setUser(res.user ?? null)
        setIsGuest(false)
        localStorage.removeItem(GUEST_KEY)
        await refresh()
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not create account')
      throw e
    }
  }

  function continueAsGuest() {
    localStorage.setItem(GUEST_KEY, '1')
    setIsGuest(true)
  }

  function signOut() {
    setToken(null)
    localStorage.removeItem(GUEST_KEY)
    setUser(null)
    setIsGuest(false)
  }

  return (
    <SessionContext.Provider value={{ user, isGuest, loading, error, login, signup, continueAsGuest, signOut, refresh }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}
