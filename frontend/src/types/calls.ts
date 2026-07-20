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

/** Mirrors backend/app/telephony/call_flow.py's MAX_ATTEMPTS and retry rule. */
export const MAX_ATTEMPTS = 3
export const RETRYABLE_STATUSES: CallStatus[] = ['no_answer', 'busy', 'failed']

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
