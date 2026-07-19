/**
 * Mock outbound-call queue.
 *
 * Nothing here is connected to the backend: `POST /api/calls/schedule` is
 * still an HTTP 501 stub (backend/app/api/calls.py), there is no list
 * endpoint yet, and `telephony.client.place_call` dials a real, billed call
 * — CLAUDE.md is explicit that it must never be smoke-tested. Once Person B's
 * queue (Celery/Redis) and `workers.place_outbound_call` land, replace this
 * with `api<QueuedCall[]>('/api/calls')` and make the "Start call" button a
 * real (confirmed) `POST /api/calls/schedule` — see docs/frontend-dashboard.md.
 */
import type { QueuedCall } from '../types/calls'

export const mockCallQueue: QueuedCall[] = [
  {
    id: 1001,
    customer_phone: '+20 10 1234 5678',
    ticket_id: 'TCK-48291',
    status: 'queued',
    outcome: null,
    attempt_number: 1,
    scheduled_at: '2026-07-20T09:00:00Z',
  },
  {
    id: 1002,
    customer_phone: '+20 12 9876 5432',
    ticket_id: 'TCK-48305',
    status: 'queued',
    outcome: null,
    attempt_number: 1,
    scheduled_at: '2026-07-20T09:15:00Z',
  },
  {
    id: 1003,
    customer_phone: '+20 11 4455 6677',
    ticket_id: 'TCK-48117',
    status: 'no_answer',
    outcome: null,
    attempt_number: 2,
    scheduled_at: '2026-07-20T08:30:00Z',
  },
  {
    id: 1004,
    customer_phone: '+20 15 2233 8899',
    ticket_id: 'TCK-48042',
    status: 'completed',
    outcome: 'resolved',
    attempt_number: 1,
    scheduled_at: '2026-07-20T08:00:00Z',
  },
  {
    id: 1005,
    customer_phone: '+20 10 5566 1122',
    ticket_id: 'TCK-48210',
    status: 'completed',
    outcome: 'transferred',
    attempt_number: 1,
    scheduled_at: '2026-07-20T08:10:00Z',
  },
  {
    id: 1006,
    customer_phone: '+20 12 3344 7788',
    ticket_id: 'TCK-47998',
    status: 'failed',
    outcome: null,
    attempt_number: 3,
    scheduled_at: '2026-07-20T07:45:00Z',
  },
]
