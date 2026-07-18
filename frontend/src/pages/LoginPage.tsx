/**
 * Mock sign-in page. Does not call the backend — there is no /api/auth/token
 * yet (backend/app/data/auth.py is unimplemented). The role selector below is
 * a temporary stand-in for what a decoded JWT will provide once Person D's
 * OAuth2/RBAC lands; see src/auth/AuthContext.tsx's TODO(auth).
 */
import { useState } from 'react'
import type { FormEvent } from 'react'
import { KeyRound, PhoneCall, ShieldAlert } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import type { Role } from '../auth/types'

export default function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('agent')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    login(email, role)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-4">
      <div className="w-full max-w-sm rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--brand)] text-white">
            <PhoneCall size={18} strokeWidth={2.25} />
          </span>
          <div>
            <h1 className="text-base font-semibold leading-tight text-[var(--text-primary)]">CallCenter Ops</h1>
            <p className="text-xs leading-tight text-[var(--text-muted)]">Sign in to continue</p>
          </div>
        </div>

        <div className="mb-5 flex items-start gap-2 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10 px-3 py-2">
          <ShieldAlert size={15} className="mt-0.5 shrink-0 text-[var(--accent)]" />
          <p className="text-xs leading-snug text-[var(--text-primary)]">
            Mock sign-in for preview only — not connected to the backend. Real authentication is wired up once
            role-based access control lands (backend/app/data/auth.py).
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
            />
          </div>

          <div>
            <label htmlFor="role" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
              Sign in as (temporary — until roles come from the backend)
            </label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
            >
              <option value="agent">Agent — Knowledge Base Assistant</option>
              <option value="quality_manager">Quality Manager — FCR Dashboard</option>
            </select>
          </div>

          <button
            type="submit"
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--brand)] px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            <KeyRound size={15} />
            Sign in
          </button>
        </form>
      </div>
    </div>
  )
}
