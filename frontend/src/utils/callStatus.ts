import type { CallStatus } from '../types/calls'
import type { StatStatus } from '../components/StatCard'

export const STATUS_LABEL: Record<CallStatus, string> = {
  queued: 'Queued',
  initiated: 'Initiated',
  ringing: 'Ringing',
  in_progress: 'In progress',
  completed: 'Completed',
  no_answer: 'No answer',
  busy: 'Busy',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

const LIVE_STATUSES: CallStatus[] = ['initiated', 'ringing', 'in_progress']

export function isLive(status: CallStatus): boolean {
  return LIVE_STATUSES.includes(status)
}

export function statusTone(status: CallStatus): StatStatus {
  if (status === 'completed') return 'good'
  if (isLive(status)) return 'warn'
  if (status === 'no_answer' || status === 'busy' || status === 'failed' || status === 'cancelled') return 'bad'
  return 'neutral' // queued
}

export const STATUS_TONE_CLASSES: Record<StatStatus, string> = {
  good: 'bg-[var(--success)]/10 text-[var(--success)]',
  warn: 'bg-[var(--accent)]/10 text-[var(--accent)]',
  bad: 'bg-[var(--danger)]/10 text-[var(--danger)]',
  neutral: 'bg-[var(--surface-muted)] text-[var(--text-muted)]',
}
