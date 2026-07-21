import type { ReactNode } from 'react'
import { LogOut, PhoneCall } from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import type { Role } from '../../auth/types'

interface Tab {
  label: string
  active: boolean
  onClick: () => void
}

interface AppShellProps {
  children: ReactNode
  /** Optional sub-page tabs (e.g. Overview/Details within the Quality Manager role). Omit for single-page roles. */
  tabs?: Tab[]
}

const ROLE_LABEL: Record<Role, string> = {
  agent: 'Agent',
  quality_manager: 'Quality Manager',
  admin: 'Admin',
}

/** Base app structure (Sprint 1): header + content container. Role determines which top-level page renders (see App.tsx); `tabs` optionally switches sub-pages within one role. */
export default function AppShell({ children, tabs }: AppShellProps) {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-[var(--surface)]">
      <header className="border-b border-[var(--border-subtle)] bg-[var(--surface-card)]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--brand)] text-white">
              <PhoneCall size={18} strokeWidth={2.25} />
            </span>
            <div>
              <h1 className="text-base font-semibold leading-tight text-[var(--text-primary)]">CallCenter Ops</h1>
              <p className="text-xs leading-tight text-[var(--text-muted)]">Outbound follow-up &amp; quality dashboard</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="rounded-full border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-muted)]">
              Sprint 2 · Preview data
            </span>

            {user && (
              <>
                <div className="flex items-center gap-2 border-l border-[var(--border-subtle)] pl-3">
                  <div className="text-right leading-tight">
                    <p className="text-xs font-medium text-[var(--text-primary)]">{user.name}</p>
                    <p className="text-[11px] text-[var(--text-muted)]">{ROLE_LABEL[user.role]}</p>
                  </div>
                  <button
                    type="button"
                    onClick={logout}
                    aria-label="Sign out"
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                  >
                    <LogOut size={15} />
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        {tabs && tabs.length > 0 && (
          <div className="mx-auto flex max-w-6xl gap-1 px-6">
            {tabs.map((tab) => (
              <button
                key={tab.label}
                type="button"
                onClick={tab.onClick}
                className={`border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                  tab.active
                    ? 'border-[var(--brand)] text-[var(--brand)]'
                    : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
