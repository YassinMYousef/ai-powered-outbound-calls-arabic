/**
 * Mock-only auth state — NOT connected to the backend.
 *
 * backend/app/data/auth.py's get_current_user() and require_role() are both
 * `raise NotImplementedError` (Person D, Sprint 3, not started yet). Until
 * that lands there is no /api/auth/token to call, so `login` below just
 * stores a role locally; it never hits the network.
 *
 * TODO(auth): once Person D ships OAuth2/RBAC, replace `login` with a real
 * `POST /api/auth/token` call, derive `user` from the decoded JWT the backend
 * returns, and call `setAuthToken(jwt)` from api/client.ts (clear it in
 * `logout`). Every reports/chat/kb/calls request already flows through that one
 * choke point, so no call site needs to change.
 */
import { createContext, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { MockUser, Role } from './types'

interface AuthContextValue {
  user: MockUser | null
  login: (email: string, role: Role) => void
  switchRole: (role: Role) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MockUser | null>(null)

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      login: (email, role) => setUser({ name: email.split('@')[0] || 'User', email, role }),
      switchRole: (role) => setUser((prev) => (prev ? { ...prev, role } : prev)),
      logout: () => setUser(null),
    }),
    [user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
