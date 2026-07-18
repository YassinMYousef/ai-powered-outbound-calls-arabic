import { LogOut, ShieldOff } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'

/** Fallback for a signed-in user whose role isn't mapped to a page. Defensive today (both roles route somewhere), load-bearing once real roles come from the backend. */
export default function UnauthorizedPage() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-4">
      <div className="w-full max-w-sm rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-6 text-center shadow-sm">
        <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--danger)]/10 text-[var(--danger)]">
          <ShieldOff size={22} />
        </span>
        <h1 className="text-base font-semibold text-[var(--text-primary)]">Access denied</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          {user ? `Your role ("${user.role}") isn't permitted to view this page.` : 'You need to sign in to view this page.'}
        </p>
        <button
          type="button"
          onClick={logout}
          className="mt-5 inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:border-[var(--brand)] hover:text-[var(--brand)]"
        >
          <LogOut size={14} />
          Back to sign in
        </button>
      </div>
    </div>
  )
}
