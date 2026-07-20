/**
 * Agent roster — quality-manager view. Real (not mock): backend/app/api/agents.py.
 * Not an auth system — data/auth.py's OAuth2/RBAC is still unimplemented, so
 * this is a roster a manager maintains, not account creation/login.
 */
import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Loader2, Trash2, UserPlus } from 'lucide-react'
import { api } from '../api/client'
import type { Agent } from '../types/agents'
import { formatDateTime } from '../utils/format'

function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      setAgents(await api<Agent[]>('/api/agents'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agents.')
    } finally {
      setLoading(false)
    }
  }

  return { agents, loading, error, refresh }
}

function AddAgentForm({ onAdded }: { onAdded: () => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api<Agent>('/api/agents', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), email: email.trim() }),
      })
      setName('')
      setEmail('')
      onAdded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add agent.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">Add agent</h3>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-2">
        <div className="min-w-[160px] flex-1">
          <label htmlFor="agent-name" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
            Name
          </label>
          <input
            id="agent-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
          />
        </div>
        <div className="min-w-[200px] flex-1">
          <label htmlFor="agent-email" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
            Email
          </label>
          <input
            id="agent-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="agent@callcenter.example"
            required
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
          />
        </div>
        <button
          type="submit"
          disabled={!name.trim() || !email.trim() || submitting}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white transition-opacity disabled:opacity-40"
        >
          <UserPlus size={14} />
          {submitting ? 'Adding…' : 'Add'}
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-[var(--danger)]">{error}</p>}
    </div>
  )
}

function DeleteAgentButton({ agent, onDeleted }: { agent: Agent; onDeleted: () => void }) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleDelete() {
    if (!window.confirm(`Remove ${agent.name} from the roster?`)) return
    setDeleting(true)
    setError(null)
    try {
      await api(`/api/agents/${agent.id}`, { method: 'DELETE' })
      onDeleted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove agent.')
      setDeleting(false)
    }
  }

  return (
    <span className="inline-flex items-center gap-1">
      <button
        type="button"
        onClick={handleDelete}
        disabled={deleting}
        aria-label={`Remove ${agent.name}`}
        className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-muted)] transition-colors hover:border-[var(--danger)] hover:text-[var(--danger)] disabled:opacity-40"
      >
        {deleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
      </button>
      {error && <span className="text-xs text-[var(--danger)]">{error}</span>}
    </span>
  )
}

export default function AgentsPage() {
  const { agents, loading, error, refresh } = useAgents()

  // Fetch once on mount — refresh's identity changes every render, so it's deliberately left out of the deps array.
  useEffect(() => {
    refresh()
  }, [])

  return (
    <>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Agents</h2>
        <p className="text-sm text-[var(--text-muted)]">
          Team roster. Not a login system — see docs/frontend-dashboard.md for the OAuth2/RBAC status.
        </p>
      </div>

      <div className="mb-4">
        <AddAgentForm onAdded={refresh} />
      </div>

      {error && <p className="mb-3 text-xs text-[var(--danger)]">{error}</p>}

      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] shadow-sm">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs text-[var(--text-muted)]">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Added</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-xs text-[var(--text-muted)]">
                  Loading agents…
                </td>
              </tr>
            )}
            {!loading && agents.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-xs text-[var(--text-muted)]">
                  No agents yet — add one above.
                </td>
              </tr>
            )}
            {agents.map((agent) => (
              <tr key={agent.id} className="border-b border-[var(--border-subtle)] last:border-0">
                <td className="px-4 py-3 text-xs font-medium text-[var(--text-primary)]">{agent.name}</td>
                <td className="font-mono-num px-4 py-3 text-xs text-[var(--text-primary)]">{agent.email}</td>
                <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDateTime(agent.created_at)}</td>
                <td className="px-4 py-3">
                  <DeleteAgentButton agent={agent} onDeleted={refresh} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
