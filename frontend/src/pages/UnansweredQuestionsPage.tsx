/**
 * Unanswered questions (KB gaps) — the questions the RAG chatbot could not answer,
 * grouped by normalized text and ranked by how often agents hit them. Wires GET
 * /api/kb/gaps + POST /api/kb/gaps/resolve (backend/app/api/kb.py). An admin reads
 * the list, uploads the missing docs on the Knowledge Base tab, then marks each
 * group Resolved (added) or Dismissed (not a real gap).
 *
 * Quality-manager surface: sits behind the dashboard alongside the Knowledge Base.
 */
import { AlertTriangle, Check, HelpCircle, Inbox, Loader2, RotateCw, X } from 'lucide-react'
import { useKbGaps } from '../hooks/useKbGaps'
import { formatDateTime } from '../utils/format'
import type { GapReason, GapStatus, KbGap } from '../types/kb'

const STATUS_TABS: { value: GapStatus; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'dismissed', label: 'Dismissed' },
]

// Verdict → human label + tone. Ordered worst-coverage first for the eye.
const REASON_META: Record<GapReason, { label: string; className: string }> = {
  no_match: { label: 'Not in KB', className: 'bg-[var(--danger)]/10 text-[var(--danger)]' },
  no_citation: { label: 'No usable passage', className: 'bg-[var(--accent)]/10 text-[var(--accent)]' },
  low_confidence: { label: 'Weak match', className: 'bg-[var(--accent)]/10 text-[var(--accent)]' },
}

function GapRow({
  gap,
  actionable,
  onResolve,
  resolving,
}: {
  gap: KbGap
  actionable: boolean
  onResolve: (status: 'resolved' | 'dismissed') => void
  resolving: boolean
}) {
  const reason = REASON_META[gap.reason] ?? REASON_META.no_match
  return (
    <li className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-muted)] text-[var(--text-muted)]">
        <HelpCircle size={16} />
      </span>

      <div className="min-w-0 flex-1">
        <p dir="rtl" className="truncate text-sm font-medium text-[var(--text-primary)]" title={gap.sample_query}>
          {gap.sample_query}
        </p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[var(--text-muted)]">
          <span className={`rounded-full px-2 py-0.5 font-medium ${reason.className}`}>{reason.label}</span>
          <span>·</span>
          <span>Last asked {formatDateTime(gap.last_seen)}</span>
          {gap.top_similarity !== null && (
            <>
              <span>·</span>
              <span>best match {gap.top_similarity.toFixed(2)}</span>
            </>
          )}
        </p>
      </div>

      <span
        className="shrink-0 rounded-full bg-[var(--brand)]/10 px-2.5 py-1 text-xs font-semibold text-[var(--brand)]"
        title={`Asked ${gap.count} time${gap.count === 1 ? '' : 's'}`}
      >
        {gap.count}× asked
      </span>

      {actionable && (
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            disabled={resolving}
            onClick={() => onResolve('resolved')}
            className="flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] px-2.5 py-1.5 text-xs font-medium text-[var(--success)] hover:border-[var(--success)] disabled:opacity-50"
          >
            {resolving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
            Resolved
          </button>
          <button
            type="button"
            disabled={resolving}
            onClick={() => onResolve('dismissed')}
            className="flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:border-[var(--text-muted)] disabled:opacity-50"
          >
            <X size={13} />
            Dismiss
          </button>
        </div>
      )}
    </li>
  )
}

export default function UnansweredQuestionsPage() {
  const { gaps, status, setStatus, loading, error, reload, resolve, resolvingKey } = useKbGaps()

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Unanswered Questions</h2>
          <p className="text-sm text-[var(--text-muted)]">
            Questions the assistant could not answer from the knowledge base, most-asked first. Fill the gap by
            uploading a document on the Knowledge Base tab, then mark it resolved.
          </p>
        </div>
        <button
          type="button"
          onClick={reload}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--brand)]"
        >
          <RotateCw size={13} />
          Refresh
        </button>
      </div>

      {/* Status filter */}
      <div className="mb-4 inline-flex gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] p-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setStatus(tab.value)}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              status === tab.value
                ? 'bg-[var(--brand)] text-white'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-8 text-sm text-[var(--text-muted)]">
          <Loader2 size={16} className="animate-spin" />
          Loading unanswered questions…
        </div>
      )}

      {!loading && error && (
        <div className="flex items-start gap-3 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/5 p-4">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[var(--danger)]" />
          <div className="flex-1">
            <p className="text-sm font-medium text-[var(--text-primary)]">Could not load unanswered questions</p>
            <p className="mt-0.5 text-xs text-[var(--text-muted)]">{error}</p>
          </div>
          <button
            type="button"
            onClick={reload}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--brand)]"
          >
            <RotateCw size={13} />
            Retry
          </button>
        </div>
      )}

      {!loading && !error && gaps.length === 0 && (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] px-4 py-10 text-center">
          <Inbox size={22} className="text-[var(--text-muted)]" />
          <p className="text-sm text-[var(--text-muted)]">
            {status === 'open'
              ? 'No open gaps — the knowledge base is answering everything asked so far.'
              : `No ${status} gaps.`}
          </p>
        </div>
      )}

      {!loading && !error && gaps.length > 0 && (
        <ul className="divide-y divide-[var(--border-subtle)] overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)]">
          {gaps.map((gap) => (
            <GapRow
              key={gap.normalized_query}
              gap={gap}
              actionable={status === 'open'}
              resolving={resolvingKey === gap.normalized_query}
              onResolve={(next) => {
                void resolve(gap.normalized_query, next).catch(() => {
                  /* error surfaced by the hook */
                })
              }}
            />
          ))}
        </ul>
      )}
    </>
  )
}
