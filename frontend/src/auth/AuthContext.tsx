/**
 * Auth state backed by the real backend (backend/app/data/auth.py).
 *
 * `login` calls POST /api/auth/token, activates the returned JWT (so every
 * api/client.ts request is authenticated), and derives `user` — including its
 * role — from GET /api/auth/me. A persisted token is restored on load. There is
 * no client-side role selection: the backend token is the sole source of truth.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { AuthUser } from './types'
import { clearToken, login as apiLogin, restoreSession } from '../api/auth'

interface AuthContextValue {
  user: AuthUser | null
  /** 'loading' while a persisted session is being restored; 'ready' afterwards. */
  status: 'loading' | 'ready'
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready'>('loading')

  useEffect(() => {
    let active = true
    restoreSession()
      .then((restored) => {
        if (active) setUser(restored)
      })
      .finally(() => {
        if (active) setStatus('ready')
      })
    return () => {
      active = false
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      login: async (username, password) => {
        setUser(await apiLogin(username, password))
      },
      logout: () => {
        clearToken()
        setUser(null)
      },
    }),
    [user, status],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
