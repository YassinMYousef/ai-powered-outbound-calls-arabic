/**
 * Outbound-call shapes — backend/app/api/calls.py (now a real implementation,
 * not the former 501 stubs). Mirrors data/models.py::CallLog and the calls
 * API's _call_dict / create_call responses.
 */

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

/** Mirrors backend/app/telephony/call_flow.py's MAX_ATTEMPTS and retry rule. */
export const MAX_ATTEMPTS = 3
export const RETRYABLE_STATUSES: CallStatus[] = ['no_answer', 'busy', 'failed']

/** POST /api/calls/schedule — enqueues a batch of outbound follow-up calls (202). */
export interface ScheduleBatchResult {
  scheduled?: number
  [key: string]: unknown
}

/** Response shape of POST /api/calls (backend/app/api/calls.py::create_call). */
export interface CreateCallResponse {
  id: number
  customer_phone: string
  ticket_id: string | null
  status: CallStatus
}

/** Mirrors backend/app/api/calls.py's _call_dict — GET /api/calls and GET /api/calls/{id}. */
export interface CallRecord {
  id: number
  customer_id: number | null
  customer_phone: string
  ticket_id: string | null
  status: CallStatus
  outcome: CallOutcome
  duration_seconds: number | null
  transcript: string | null
  attempt_number: number
  provider_call_sid: string | null
  created_at: string // ISO
}

/**
 * GET /api/calls/{call_id} — the logged outcome/duration/transcript of one call,
 * as consumed by the Operations lookup. A structural subset of CallRecord.
 */
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
