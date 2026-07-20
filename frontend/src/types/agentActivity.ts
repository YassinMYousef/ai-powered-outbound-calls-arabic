/**
 * Manager-facing agent roster + activity feed.
 *
 * Mock only, by necessity: backend/app/data/models.py's CallLog has no
 * agent-identity column yet (outbound calls are AI-driven; a human agent is
 * only ever involved via call_flow.transfer_to_agent, which doesn't persist
 * who picked up). There is no per-agent data to fetch until that's added.
 */
export interface AgentSummary {
  id: string
  name: string
  email: string
  callsHandled: number
  resolvedCount: number
  kbQueries: number
  lastActiveAt: string // ISO
}

export type ActivityEventType =
  | 'call_started'
  | 'call_resolved'
  | 'call_unresolved'
  | 'call_transferred'
  | 'call_failed'
  | 'kb_query'

export interface ActivityEvent {
  id: string
  agentId: string
  type: ActivityEventType
  description: string
  at: string // ISO
}
