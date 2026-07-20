/**
 * Places a REAL, billed outbound call via POST /api/calls (backend/app/api/calls.py),
 * which persists a CallLog row and enqueues telephony.workers.place_outbound_call.
 * For a number that isn't already a CRM customer with a queued row — for an
 * existing queued row, use the "Start call" button in CallQueuePage's table
 * instead. Requires an explicit browser confirm() before sending — this
 * dials a phone and costs money the moment it's used.
 */
import { useState } from 'react'
import type { FormEvent } from 'react'
import { AlertTriangle, PhoneCall } from 'lucide-react'
import { api } from '../api/client'
import type { CreateCallResponse } from '../types/calls'

interface PlaceRealCallFormProps {
  onCreated?: () => void
}

export default function PlaceRealCallForm({ onCreated }: PlaceRealCallFormProps) {
  const [phone, setPhone] = useState('')
  const [ticketId, setTicketId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [placed, setPlaced] = useState<CreateCallResponse | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmedPhone = phone.trim()
    if (!trimmedPhone) return

    const confirmed = window.confirm(
      `This dials ${trimmedPhone} through Twilio right now and bills the configured account. Continue?`,
    )
    if (!confirmed) return

    setSubmitting(true)
    setError(null)
    setPlaced(null)
    try {
      const result = await api<CreateCallResponse>('/api/calls', {
        method: 'POST',
        body: JSON.stringify({ customer_phone: trimmedPhone, ticket_id: ticketId.trim() || null }),
      })
      setPlaced(result)
      setPhone('')
      setTicketId('')
      onCreated?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to place the call.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-xl border border-[var(--danger)]/30 bg-[var(--surface-card)] p-5 shadow-sm">
      <div className="mb-3 flex items-start gap-2">
        <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[var(--danger)]" />
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Place a real call</h3>
          <p className="text-xs text-[var(--text-muted)]">
            Dials through Twilio for real and bills the configured account. Only use a number you have consent to
            call — e.g. your own phone, or a Twilio-verified caller ID.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[180px]">
          <label htmlFor="real-call-phone" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
            Phone number (E.164)
          </label>
          <input
            id="real-call-phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+201091894094"
            required
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--danger)] focus:ring-2 focus:ring-[var(--danger)]/20"
          />
        </div>
        <div className="flex-1 min-w-[140px]">
          <label htmlFor="real-call-ticket" className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
            Ticket ID (optional)
          </label>
          <input
            id="real-call-ticket"
            value={ticketId}
            onChange={(e) => setTicketId(e.target.value)}
            placeholder="TCK-48291"
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--danger)] focus:ring-2 focus:ring-[var(--danger)]/20"
          />
        </div>
        <button
          type="submit"
          disabled={!phone.trim() || submitting}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--danger)] px-4 py-2 text-sm font-medium text-white transition-opacity disabled:opacity-40"
        >
          <PhoneCall size={14} />
          {submitting ? 'Calling…' : 'Call now'}
        </button>
      </form>

      {error && <p className="mt-3 text-xs text-[var(--danger)]">{error}</p>}
      {placed && (
        <p className="mt-3 text-xs text-[var(--success)]">
          Call #{placed.id} to {placed.customer_phone} queued for dialing — status: {placed.status}.
        </p>
      )}
    </div>
  )
}
