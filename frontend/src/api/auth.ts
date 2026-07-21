/**
 * Real authentication against the backend (backend/app/api/auth.py):
 *   POST /api/auth/token  — exchange username+password for a JWT
 *   GET  /api/auth/me     — the current user behind an activated token
 *
 * The JWT is persisted to localStorage and activated via setAuthToken so every
 * request through api/client.ts carries `Authorization: Bearer <jwt>`. Role is
 * always taken from the backend — never chosen client-side.
 */
import { api, setAuthToken } from './client'
import type { AuthUser, Role } from '../auth/types'

const TOKEN_KEY = 'cc_auth_token'

interface TokenResponse {
  access_token: string
  token_type: string
  role: Role
}

interface MeResponse {
  id: number
  username: string
  full_name: string
  email: string
  role: Role
}

function activateToken(token: string): void {
  setAuthToken(token)
  localStorage.setItem(TOKEN_KEY, token)
}

/** Drop the active session — clears the in-memory token and the persisted copy. */
export function clearToken(): void {
  setAuthToken(null)
  localStorage.removeItem(TOKEN_KEY)
}

/** The current user for an already-activated token. */
export async function fetchMe(): Promise<AuthUser> {
  const me = await api<MeResponse>('/api/auth/me')
  return { name: me.full_name || me.username, email: me.email, role: me.role }
}

/** Exchange credentials for a JWT, activate it, and return the signed-in user.
 *  The token endpoint is OAuth2 password flow → form-urlencoded, not JSON. */
export async function login(username: string, password: string): Promise<AuthUser> {
  const token = await api<TokenResponse>('/api/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username, password }).toString(),
  })
  activateToken(token.access_token)
  return fetchMe()
}

/** Reuse a persisted token on app load; clears it if it no longer validates. */
export async function restoreSession(): Promise<AuthUser | null> {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) return null
  setAuthToken(token)
  try {
    return await fetchMe()
  } catch {
    clearToken()
    return null
  }
}
