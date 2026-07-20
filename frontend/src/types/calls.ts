/**
 * Outbound-call shapes (backend/app/api/calls.py).
 *
 * NOTE: both call endpoints are 501 stubs today, so these shapes are the
 * expected contract derived from data/models.py::CallLog, not yet a live
 * response. Kept here so the frontend consumes them the moment the backend
 * (app/workers/tasks.py) lands.
 */

/** POST /api/calls/schedule — enqueues a batch of outbound follow-up calls (202). */
export interface ScheduleBatchResult {
  scheduled?: number
  [key: string]: unknown
}

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

export type CallOutcome = 'resolved' | 'unresolved' | 'transferred' | 'unknown'

/** GET /api/calls/{call_id} — the logged outcome/duration/transcript of one call. */
export interface CallDetail {
  id: number
  customer_phone: string
  ticket_id: string | null
  status: CallStatus
  outcome: CallOutcome | null
  duration_seconds: number | null
  transcript: string | null
  attempt_number: number
  created_at: string | null
}
