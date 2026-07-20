/**
 * Scheduled calls + queue, for the agent role. Real data — GET /api/calls —
 * and a real per-row dial: POST /api/calls/{id}/dial (backend/app/api/calls.py).
 * A customer flagged for follow-up on the manager's Customers tab shows up
 * here as a "queued" row.
 */
import { useEffect, useState } from 'react'
import { Loader2, PhoneCall, RefreshCw } from 'lucide-react'
import type { CallRecord } from '../types/calls'
import { STATUS_LABEL, STATUS_TONE_CLASSES, isLive, statusTone } from '../utils/callStatus'
import { formatDateTime } from '../utils/format'
import { api } from '../api/client'
import PlaceRealCallForm from '../components/PlaceRealCallForm'

function StatusBadge({ status }: { status: CallRecord['status'] }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_TONE_CLASSES[statusTone(status)]}`}>
      {isLive(status) && <Loader2 size={10} className="animate-spin" />}
      {STATUS_LABEL[status]}
    </span>
  )
}

export default function CallQueuePage() {
  const [calls, setCalls] = useState<CallRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dialingId, setDialingId] = useState<number | null>(null)

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      setCalls(await api<CallRecord[]>('/api/calls'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load calls.')
    } finally {
      setLoading(false)
    }
  }

  // Fetch once on mount — this component remounts every time the Call Queue tab is opened, which is when a refresh is wanted.
  useEffect(() => {
    refresh()
  }, [])

  async function startCall(call: CallRecord) {
    const confirmed = window.confirm(`This dials ${call.customer_phone} through Twilio right now. Continue?`)
    if (!confirmed) return

    setDialingId(call.id)
    try {
      await api(`/api/calls/${call.id}/dial`, { method: 'POST' })
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start the call.')
    } finally {
      setDialingId(null)
    }
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Call Queue</h2>
          <p className="text-sm text-[var(--text-muted)]">Scheduled follow-up calls and their live status.</p>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition-colors hover:border-[var(--brand)] hover:text-[var(--brand)]"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : undefined} />
          Refresh
        </button>
      </div>

      {error && <p className="mb-3 text-xs text-[var(--danger)]">{error}</p>}

      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] shadow-sm">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs text-[var(--text-muted)]">
              <th className="px-4 py-3 font-medium">Ticket</th>
              <th className="px-4 py-3 font-medium">Phone</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Outcome</th>
              <th className="px-4 py-3 font-medium">Attempt</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-xs text-[var(--text-muted)]">
                  Loading calls…
                </td>
              </tr>
            )}
            {!loading && calls.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-xs text-[var(--text-muted)]">
                  No calls yet — flag a customer for follow-up on the Customers tab, or place one below.
                </td>
              </tr>
            )}
            {calls.map((call) => (
              <tr key={call.id} className="border-b border-[var(--border-subtle)] last:border-0">
                <td className="px-4 py-3 font-mono-num text-xs text-[var(--text-primary)]">{call.ticket_id ?? '—'}</td>
                <td className="font-mono-num px-4 py-3 text-xs text-[var(--text-primary)]">{call.customer_phone}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={call.status} />
                </td>
                <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{call.outcome ?? '—'}</td>
                <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{call.attempt_number}</td>
                <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDateTime(call.created_at)}</td>
                <td className="px-4 py-3">
                  {call.status === 'queued' && (
                    <button
                      type="button"
                      onClick={() => startCall(call)}
                      disabled={dialingId === call.id}
                      className="inline-flex items-center gap-1 rounded-lg bg-[var(--brand)] px-2.5 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                    >
                      {dialingId === call.id ? <Loader2 size={12} className="animate-spin" /> : <PhoneCall size={12} />}
                      Start call
                    </button>
                  )}
                  {isLive(call.status) && <span className="text-xs text-[var(--text-muted)]">Call in progress</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4">
        <PlaceRealCallForm onCreated={refresh} />
      </div>
    </>
  )
}
