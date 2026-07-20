/**
 * CRM customer records — quality-manager view. Genuinely wired to the backend
 * (backend/app/api/customers.py), not mock data: this is the "CRM / Inbound
 * Call Records" system the requirements doc names but never defines — see
 * docs/frontend-dashboard.md for why it was built as a real module here
 * instead of a stand-in import endpoint.
 */
import { Fragment, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ChevronDown, ChevronRight, Flag, Loader2, Trash2, UserPlus } from 'lucide-react'
import { api } from '../api/client'
import type { Customer, CustomerDetail } from '../types/customers'
import { STATUS_LABEL, STATUS_TONE_CLASSES, statusTone } from '../utils/callStatus'
import type { CallStatus } from '../types/calls'
import { formatDateTime } from '../utils/format'

function useCustomers() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      setCustomers(await api<Customer[]>('/api/customers'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load customers.')
    } finally {
      setLoading(false)
    }
  }

  return { customers, loading, error, refresh }
}

function AddCustomerForm({ onAdded }: { onAdded: () => void }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api<Customer>('/api/customers', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), phone: phone.trim(), notes: notes.trim() || null }),
      })
      setName('')
      setPhone('')
      setNotes('')
      onAdded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add customer.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">Add customer</h3>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-2">
        <div className="min-w-[140px] flex-1">
          <label htmlFor="cust-name" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
            Name
          </label>
          <input
            id="cust-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
          />
        </div>
        <div className="min-w-[160px] flex-1">
          <label htmlFor="cust-phone" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
            Phone (E.164)
          </label>
          <input
            id="cust-phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+201091894094"
            required
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
          />
        </div>
        <div className="min-w-[160px] flex-[2]">
          <label htmlFor="cust-notes" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
            Notes (optional)
          </label>
          <input
            id="cust-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
          />
        </div>
        <button
          type="submit"
          disabled={!name.trim() || !phone.trim() || submitting}
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

function FlagButton({ customerId, onFlagged }: { customerId: number; onFlagged: () => void }) {
  const [open, setOpen] = useState(false)
  const [ticketId, setTicketId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFlag(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api(`/api/customers/${customerId}/flag`, {
        method: 'POST',
        body: JSON.stringify({ ticket_id: ticketId.trim() || null }),
      })
      setOpen(false)
      setTicketId('')
      onFlagged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to flag customer.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-primary)] transition-colors hover:border-[var(--brand)] hover:text-[var(--brand)]"
      >
        <Flag size={12} />
        Flag for follow-up
      </button>
    )
  }

  return (
    <form onSubmit={handleFlag} className="flex items-center gap-1.5">
      <input
        value={ticketId}
        onChange={(e) => setTicketId(e.target.value)}
        placeholder="Ticket ID (optional)"
        autoFocus
        className="w-32 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-2 py-1 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--brand)]"
      />
      <button
        type="submit"
        disabled={submitting}
        className="inline-flex items-center gap-1 rounded-lg bg-[var(--brand)] px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-40"
      >
        {submitting ? <Loader2 size={12} className="animate-spin" /> : <Flag size={12} />}
        Confirm
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
      >
        Cancel
      </button>
      {error && <span className="text-xs text-[var(--danger)]">{error}</span>}
    </form>
  )
}

function DeleteButton({ customer, onDeleted }: { customer: Customer; onDeleted: () => void }) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleDelete() {
    if (!window.confirm(`Delete ${customer.name}? Their past call history is kept, just unlinked.`)) return
    setDeleting(true)
    setError(null)
    try {
      await api(`/api/customers/${customer.id}`, { method: 'DELETE' })
      onDeleted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete customer.')
      setDeleting(false)
    }
  }

  return (
    <span className="inline-flex items-center gap-1">
      <button
        type="button"
        onClick={handleDelete}
        disabled={deleting}
        aria-label={`Delete ${customer.name}`}
        className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-muted)] transition-colors hover:border-[var(--danger)] hover:text-[var(--danger)] disabled:opacity-40"
      >
        {deleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
      </button>
      {error && <span className="text-xs text-[var(--danger)]">{error}</span>}
    </span>
  )
}

function CustomerHistoryRow({ customerId }: { customerId: number }) {
  const [detail, setDetail] = useState<CustomerDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api<CustomerDetail>(`/api/customers/${customerId}`)
      .then(setDetail)
      .finally(() => setLoading(false))
  }, [customerId])

  if (loading) return <p className="px-4 py-3 text-xs text-[var(--text-muted)]">Loading history…</p>
  if (!detail || detail.call_history.length === 0) {
    return <p className="px-4 py-3 text-xs text-[var(--text-muted)]">No follow-up calls yet.</p>
  }

  return (
    <div className="space-y-1.5 px-4 py-3">
      {detail.call_history.map((call) => (
        <div key={call.id} className="flex items-center gap-2 text-xs">
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_TONE_CLASSES[statusTone(call.status as CallStatus)]}`}
          >
            {STATUS_LABEL[call.status as CallStatus] ?? call.status}
          </span>
          <span className="text-[var(--text-muted)]">{call.ticket_id ?? '—'}</span>
          <span className="text-[var(--text-muted)]">{formatDateTime(call.created_at)}</span>
          {call.outcome && <span className="text-[var(--text-muted)]">· {call.outcome}</span>}
        </div>
      ))}
    </div>
  )
}

export default function CustomersPage() {
  const { customers, loading, error, refresh } = useCustomers()
  const [expanded, setExpanded] = useState<number | null>(null)

  // Fetch once on mount — refresh's identity changes every render, so it's deliberately left out of the deps array.
  useEffect(() => {
    refresh()
  }, [])

  return (
    <>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Customers</h2>
        <p className="text-sm text-[var(--text-muted)]">
          CRM records and follow-up flagging. Flagging queues a call for the agent's Call Queue.
        </p>
      </div>

      <div className="mb-4">
        <AddCustomerForm onAdded={refresh} />
      </div>

      {error && <p className="mb-3 text-xs text-[var(--danger)]">{error}</p>}

      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] shadow-sm">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs text-[var(--text-muted)]">
              <th className="w-8 px-4 py-3" />
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Phone</th>
              <th className="px-4 py-3 font-medium">Notes</th>
              <th className="px-4 py-3 font-medium">Added</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-xs text-[var(--text-muted)]">
                  Loading customers…
                </td>
              </tr>
            )}
            {!loading && customers.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-xs text-[var(--text-muted)]">
                  No customers yet — add one above.
                </td>
              </tr>
            )}
            {customers.map((customer) => (
              <Fragment key={customer.id}>
                <tr className="border-b border-[var(--border-subtle)] last:border-0">
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setExpanded(expanded === customer.id ? null : customer.id)}
                      className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                      aria-label="Toggle call history"
                    >
                      {expanded === customer.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-xs font-medium text-[var(--text-primary)]">{customer.name}</td>
                  <td className="font-mono-num px-4 py-3 text-xs text-[var(--text-primary)]">{customer.phone}</td>
                  <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{customer.notes ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDateTime(customer.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FlagButton customerId={customer.id} onFlagged={refresh} />
                      <DeleteButton customer={customer} onDeleted={refresh} />
                    </div>
                  </td>
                </tr>
                {expanded === customer.id && (
                  <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface)] last:border-0">
                    <td />
                    <td colSpan={5}>
                      <CustomerHistoryRow customerId={customer.id} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
