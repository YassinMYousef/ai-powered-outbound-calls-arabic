/**
 * Scheduled calls + queue, for the agent role.
 *
 * The table below is still local/simulated mock data (data/mockCalls.ts) —
 * there's still no GET list endpoint, so there's nothing real to populate it
 * from yet. But POST /api/calls now exists and really dials through Twilio
 * (backend/app/api/calls.py), so PlaceRealCallForm below the table is wired
 * to it for real — kept as a visually separate, explicitly confirmed control
 * so it can never be confused with the mock table's "Start call" buttons.
 */
import { useState } from 'react'
import { Loader2, PhoneCall, PhoneOff, ShieldAlert } from 'lucide-react'
import type { CallOutcome, CallStatus, QueuedCall } from '../types/calls'
import { MAX_ATTEMPTS, RETRYABLE_STATUSES } from '../types/calls'
import { STATUS_LABEL, isLive, statusTone } from '../utils/callStatus'
import { mockCallQueue } from '../data/mockCalls'
import { formatDateTime } from '../utils/format'
import PlaceRealCallForm from '../components/PlaceRealCallForm'

const STATUS_TONE_CLASSES: Record<ReturnType<typeof statusTone>, string> = {
  good: 'bg-[var(--success)]/10 text-[var(--success)]',
  warn: 'bg-[var(--accent)]/10 text-[var(--accent)]',
  bad: 'bg-[var(--danger)]/10 text-[var(--danger)]',
  neutral: 'bg-[var(--surface-muted)] text-[var(--text-muted)]',
}

const EDITABLE_STATUSES: CallStatus[] = ['completed', 'no_answer', 'busy', 'failed', 'cancelled']
const OUTCOME_OPTIONS: NonNullable<CallOutcome>[] = ['resolved', 'unresolved', 'transferred', 'unknown']

function StatusBadge({ status }: { status: CallStatus }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_TONE_CLASSES[statusTone(status)]}`}>
      {isLive(status) && <Loader2 size={10} className="animate-spin" />}
      {STATUS_LABEL[status]}
    </span>
  )
}

export default function CallQueuePage() {
  const [calls, setCalls] = useState<QueuedCall[]>(mockCallQueue)

  function updateCall(id: number, patch: Partial<QueuedCall>) {
    setCalls((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)))
  }

  /** Client-side simulation only — see file header. Not a real dial. */
  function simulateCall(call: QueuedCall) {
    const isRetry = call.status !== 'queued'
    updateCall(call.id, { status: 'initiated', outcome: null, attempt_number: isRetry ? call.attempt_number + 1 : call.attempt_number })

    setTimeout(() => updateCall(call.id, { status: 'ringing' }), 600)
    setTimeout(() => updateCall(call.id, { status: 'in_progress' }), 1400)
    setTimeout(() => {
      const roll = Math.random()
      if (roll < 0.15) {
        updateCall(call.id, { status: 'no_answer' })
      } else if (roll < 0.25) {
        updateCall(call.id, { status: 'failed' })
      } else {
        const outcomes: NonNullable<CallOutcome>[] = ['resolved', 'unresolved', 'transferred']
        const outcome = outcomes[Math.floor(Math.random() * outcomes.length)]
        updateCall(call.id, { status: 'completed', outcome })
      }
    }, 2600)
  }

  return (
    <>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Call Queue</h2>
        <p className="text-sm text-[var(--text-muted)]">Scheduled follow-up calls and their live status.</p>
      </div>

      <div className="mb-4 flex items-start gap-2 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10 px-3 py-2">
        <ShieldAlert size={15} className="mt-0.5 shrink-0 text-[var(--accent)]" />
        <p className="text-xs leading-snug text-[var(--text-primary)]">
          This table is still simulated sample data — there's no list endpoint yet, so "Start call" / "Retry" here
          just plays out a status progression locally and dials nothing. To place an actual call, use "Place a real
          call" below, which is genuinely wired to Twilio.
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] shadow-sm">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs text-[var(--text-muted)]">
              <th className="px-4 py-3 font-medium">Ticket</th>
              <th className="px-4 py-3 font-medium">Phone</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Outcome</th>
              <th className="px-4 py-3 font-medium">Attempt</th>
              <th className="px-4 py-3 font-medium">Scheduled</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((call) => {
              const canRetry = RETRYABLE_STATUSES.includes(call.status) && call.attempt_number < MAX_ATTEMPTS
              const canStart = call.status === 'queued'
              const isEditable = EDITABLE_STATUSES.includes(call.status) && !isLive(call.status)

              return (
                <tr key={call.id} className="border-b border-[var(--border-subtle)] last:border-0">
                  <td className="px-4 py-3 font-mono-num text-xs text-[var(--text-primary)]">{call.ticket_id ?? '—'}</td>
                  <td className="font-mono-num px-4 py-3 text-xs text-[var(--text-primary)]">{call.customer_phone}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={call.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{call.outcome ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-[var(--text-muted)]">
                    {call.attempt_number} / {MAX_ATTEMPTS}
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDateTime(call.scheduled_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {(canStart || canRetry) && (
                        <button
                          type="button"
                          onClick={() => simulateCall(call)}
                          className="inline-flex items-center gap-1 rounded-lg bg-[var(--brand)] px-2.5 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
                        >
                          <PhoneCall size={12} />
                          {canStart ? 'Start call' : 'Retry'}
                        </button>
                      )}

                      {isLive(call.status) && (
                        <span className="inline-flex items-center gap-1 text-xs text-[var(--text-muted)]">
                          <PhoneOff size={12} className="opacity-40" />
                          Call in progress
                        </span>
                      )}

                      {isEditable && (
                        <>
                          <select
                            value={call.status}
                            onChange={(e) => {
                              const status = e.target.value as CallStatus
                              updateCall(call.id, { status, outcome: status === 'completed' ? call.outcome : null })
                            }}
                            title="Override the final status"
                            className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-1.5 py-1 text-[11px] text-[var(--text-primary)] outline-none"
                          >
                            {EDITABLE_STATUSES.map((s) => (
                              <option key={s} value={s}>
                                {STATUS_LABEL[s]}
                              </option>
                            ))}
                          </select>

                          {call.status === 'completed' && (
                            <select
                              value={call.outcome ?? 'unknown'}
                              onChange={(e) => updateCall(call.id, { outcome: e.target.value as CallOutcome })}
                              title="Override the outcome"
                              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-1.5 py-1 text-[11px] text-[var(--text-primary)] outline-none"
                            >
                              {OUTCOME_OPTIONS.map((o) => (
                                <option key={o} value={o}>
                                  {o}
                                </option>
                              ))}
                            </select>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4">
        <PlaceRealCallForm />
      </div>
    </>
  )
}
