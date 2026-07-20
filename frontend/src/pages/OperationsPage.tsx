/**
 * Operations — the call-orchestration and reporting actions that back the
 * outbound-follow-up product. Wires the three endpoints that are still backend
 * 501 stubs today (app/api/calls.py, reports.get_fcr): scheduling a call batch,
 * generating the FCR report, and looking up a single call. Each degrades to a
 * clear "not available yet" notice until the backend lands, then works as-is.
 */
import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { AlertTriangle, CalendarClock, FileBarChart, Loader2, PhoneCall, Search } from 'lucide-react'
import { describeError } from '../api/client'
import { getFcrReport } from '../api/reports'
import { scheduleFollowUpBatch, getCall } from '../api/calls'
import type { FcrReport } from '../types/reports'
import type { CallDetail, ScheduleBatchResult } from '../types/calls'
import { formatDateTime, formatDuration, formatPercent } from '../utils/format'

function Notice({ text }: { text: string }) {
  return (
    <div className="mt-3 flex items-start gap-2 rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/5 px-3 py-2">
      <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[var(--danger)]" />
      <p className="text-xs text-[var(--text-primary)]">{text}</p>
    </div>
  )
}

function Card({
  icon,
  title,
  description,
  children,
}: {
  icon: ReactNode
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5">
      <div className="mb-4 flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--brand)]/10 text-[var(--brand)]">
          {icon}
        </span>
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
          <p className="text-xs text-[var(--text-muted)]">{description}</p>
        </div>
      </div>
      {children}
    </section>
  )
}

const btn =
  'flex items-center justify-center gap-1.5 rounded-lg bg-[var(--brand)] px-3.5 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40'

function ScheduleBatchCard() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScheduleBatchResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await scheduleFollowUpBatch())
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card
      icon={<CalendarClock size={17} />}
      title="Schedule follow-up batch"
      description="Enqueue outbound calls for every customer currently flagged for follow-up."
    >
      <button type="button" onClick={run} disabled={loading} className={btn}>
        {loading ? <Loader2 size={15} className="animate-spin" /> : <CalendarClock size={15} />}
        Schedule batch
      </button>
      {result && (
        <p className="mt-3 rounded-lg border border-[var(--success)]/30 bg-[var(--success)]/5 px-3 py-2 text-xs text-[var(--text-primary)]">
          {typeof result.scheduled === 'number'
            ? `Enqueued ${result.scheduled} call${result.scheduled === 1 ? '' : 's'}.`
            : 'Batch accepted.'}
        </p>
      )}
      {error && <Notice text={error} />}
    </Card>
  )
}

function FcrReportCard() {
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState<FcrReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setLoading(true)
    setError(null)
    setReport(null)
    try {
      setReport(await getFcrReport())
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card
      icon={<FileBarChart size={17} />}
      title="First Call Resolutions report"
      description="Compile the quality team's FCR report for the latest reporting window."
    >
      <button type="button" onClick={run} disabled={loading} className={btn}>
        {loading ? <Loader2 size={15} className="animate-spin" /> : <FileBarChart size={15} />}
        Generate report
      </button>
      {report && (
        <div className="mt-3 space-y-3">
          <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div>
              <dt className="text-[var(--text-muted)]">Total calls</dt>
              <dd className="font-medium text-[var(--text-primary)]">{report.total_calls}</dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">FCR rate</dt>
              <dd className="font-medium text-[var(--text-primary)]">
                {report.fcr_rate === null ? '—' : formatPercent(report.fcr_rate)}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">Completion</dt>
              <dd className="font-medium text-[var(--text-primary)]">
                {report.completion_rate === null ? '—' : formatPercent(report.completion_rate)}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">Avg. handle time</dt>
              <dd className="font-medium text-[var(--text-primary)]">
                {report.average_handle_time_seconds === null
                  ? '—'
                  : formatDuration(report.average_handle_time_seconds)}
              </dd>
            </div>
          </dl>
          {report.report_markdown && (
            <pre
              dir="rtl"
              className="font-arabic max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] p-3 text-xs text-[var(--text-primary)]"
            >
              {report.report_markdown}
            </pre>
          )}
        </div>
      )}
      {error && <Notice text={error} />}
    </Card>
  )
}

function CallLookupCard() {
  const [id, setId] = useState('')
  const [loading, setLoading] = useState(false)
  const [call, setCall] = useState<CallDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(e: FormEvent) {
    e.preventDefault()
    const callId = Number(id)
    if (!Number.isInteger(callId) || callId <= 0) return
    setLoading(true)
    setError(null)
    setCall(null)
    try {
      setCall(await getCall(callId))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card
      icon={<PhoneCall size={17} />}
      title="Look up a call"
      description="Fetch the logged outcome, duration, and transcript for one call by its ID."
    >
      <form onSubmit={run} className="flex items-center gap-2">
        <input
          value={id}
          onChange={(e) => setId(e.target.value)}
          inputMode="numeric"
          placeholder="Call ID"
          className="w-32 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
        />
        <button type="submit" disabled={loading || !id.trim()} className={btn}>
          {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
          Look up
        </button>
      </form>
      {call && (
        <div className="mt-3 space-y-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] p-3">
          <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div>
              <dt className="text-[var(--text-muted)]">Status</dt>
              <dd className="font-medium text-[var(--text-primary)]">{call.status}</dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">Outcome</dt>
              <dd className="font-medium text-[var(--text-primary)]">{call.outcome ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">Duration</dt>
              <dd className="font-medium text-[var(--text-primary)]">
                {call.duration_seconds === null ? '—' : formatDuration(call.duration_seconds)}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">Attempt</dt>
              <dd className="font-medium text-[var(--text-primary)]">#{call.attempt_number}</dd>
            </div>
            <div className="col-span-2 sm:col-span-4">
              <dt className="text-[var(--text-muted)]">Customer</dt>
              <dd className="font-medium text-[var(--text-primary)]">
                {call.customer_phone}
                {call.ticket_id ? ` · ticket ${call.ticket_id}` : ''} · {formatDateTime(call.created_at)}
              </dd>
            </div>
          </dl>
          {call.transcript && (
            <pre
              dir="rtl"
              className="font-arabic max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] p-3 text-xs text-[var(--text-primary)]"
            >
              {call.transcript}
            </pre>
          )}
        </div>
      )}
      {error && <Notice text={error} />}
    </Card>
  )
}

export default function OperationsPage() {
  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Operations</h2>
        <p className="text-sm text-[var(--text-muted)]">
          Outbound call orchestration and reporting actions.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ScheduleBatchCard />
        <FcrReportCard />
        <div className="lg:col-span-2">
          <CallLookupCard />
        </div>
      </div>
    </>
  )
}
