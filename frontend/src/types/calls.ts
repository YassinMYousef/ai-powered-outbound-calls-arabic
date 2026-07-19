/** Mirrors backend/app/data/models.py's CallLog check constraints. */
export type CallStatus =
  | 'queued'
  | 'initiated'
  | 'ringing'
  | 'in_progress'
  | 'completed'
  | 'no_answer'
  | 'busy'
  | 'failed'
  | 'cancelled'

export type CallOutcome = 'resolved' | 'unresolved' | 'transferred' | 'unknown' | null

export interface QueuedCall {
  id: number
  customer_phone: string
  ticket_id: string | null
  status: CallStatus
  outcome: CallOutcome
  attempt_number: number
  scheduled_at: string // ISO
}

/** Mirrors backend/app/telephony/call_flow.py's MAX_ATTEMPTS and retry rule. */
export const MAX_ATTEMPTS = 3
export const RETRYABLE_STATUSES: CallStatus[] = ['no_answer', 'busy', 'failed']
