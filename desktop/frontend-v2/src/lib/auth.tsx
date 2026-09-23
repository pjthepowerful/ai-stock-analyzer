import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, setToken, type AuthResult, type AuthUser } from './api'

interface Session {
  user: AuthUser | null
  isGuest: boolean
  loading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (username: string, email: string, password: string) => Promise<void>
  continueAsGuest: () => void
  signOut: () => void
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
      .get<{ ok: boolean; user: AuthUser }>('/api/auth/me')
      .then((res) => setUser(res.user))
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    setError(null)
    try {
      const res = await api.post<AuthResult>('/api/auth/login', { email, password })
      if (res.token) {
        setToken(res.token)
        setUser(res.user ?? null)
        setIsGuest(false)
        localStorage.removeItem(GUEST_KEY)
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
    <SessionContext.Provider value={{ user, isGuest, loading, error, login, signup, continueAsGuest, signOut }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}
