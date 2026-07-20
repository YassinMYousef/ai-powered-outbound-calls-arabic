/** Outbound-call endpoints — backend/app/api/calls.py (both 501 stubs today). */
import { api } from './client'
import type { CallDetail, ScheduleBatchResult } from '../types/calls'

/** POST /api/calls/schedule — enqueue outbound follow-up calls for flagged
 *  customers. Backend stub returns 501 until app/workers/tasks.py lands. */
export function scheduleFollowUpBatch(): Promise<ScheduleBatchResult> {
  return api<ScheduleBatchResult>('/api/calls/schedule', { method: 'POST' })
}

/** GET /api/calls/{call_id} — logged outcome/duration/transcript for one call.
 *  Backend stub returns 501; 404 once implemented for an unknown id. */
export function getCall(callId: number): Promise<CallDetail> {
  return api<CallDetail>(`/api/calls/${callId}`)
}
