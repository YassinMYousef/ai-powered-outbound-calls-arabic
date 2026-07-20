import type { ActivityEvent, AgentSummary } from '../types/agentActivity'

export const mockAgents: AgentSummary[] = [
  {
    id: 'agt-1',
    name: 'Mona Ali',
    email: 'mona.ali@callcenter.example',
    callsHandled: 18,
    resolvedCount: 15,
    kbQueries: 7,
    lastActiveAt: '2026-07-20T09:12:00Z',
  },
  {
    id: 'agt-2',
    name: 'Ahmed Nabil',
    email: 'ahmed.nabil@callcenter.example',
    callsHandled: 24,
    resolvedCount: 19,
    kbQueries: 11,
    lastActiveAt: '2026-07-20T09:05:00Z',
  },
  {
    id: 'agt-3',
    name: 'Sara Youssef',
    email: 'sara.youssef@callcenter.example',
    callsHandled: 12,
    resolvedCount: 11,
    kbQueries: 3,
    lastActiveAt: '2026-07-20T08:47:00Z',
  },
  {
    id: 'agt-4',
    name: 'Karim Adel',
    email: 'karim.adel@callcenter.example',
    callsHandled: 9,
    resolvedCount: 5,
    kbQueries: 14,
    lastActiveAt: '2026-07-20T07:58:00Z',
  },
]

export const mockActivity: ActivityEvent[] = [
  { id: 'ev-1', agentId: 'agt-1', type: 'call_started', description: 'Started follow-up call — TCK-48291', at: '2026-07-20T09:12:00Z' },
  { id: 'ev-2', agentId: 'agt-1', type: 'kb_query', description: 'Asked the KB assistant: "كيف أعيد تعيين كلمة مرور العميل؟"', at: '2026-07-20T09:08:00Z' },
  { id: 'ev-3', agentId: 'agt-1', type: 'call_resolved', description: 'Call resolved on first attempt — TCK-48117', at: '2026-07-20T08:51:00Z' },
  { id: 'ev-4', agentId: 'agt-1', type: 'call_started', description: 'Started follow-up call — TCK-48117', at: '2026-07-20T08:44:00Z' },

  { id: 'ev-5', agentId: 'agt-2', type: 'call_transferred', description: 'Escalated to human agent after 2 uncertain replies — TCK-48042', at: '2026-07-20T09:05:00Z' },
  { id: 'ev-6', agentId: 'agt-2', type: 'kb_query', description: 'Asked the KB assistant: "ما هي سياسة الاسترجاع؟"', at: '2026-07-20T08:59:00Z' },
  { id: 'ev-7', agentId: 'agt-2', type: 'call_unresolved', description: 'Call ended unresolved — customer asked to be called back — TCK-48305', at: '2026-07-20T08:50:00Z' },
  { id: 'ev-8', agentId: 'agt-2', type: 'call_started', description: 'Started follow-up call — TCK-48305', at: '2026-07-20T08:41:00Z' },

  { id: 'ev-9', agentId: 'agt-3', type: 'call_resolved', description: 'Call resolved on first attempt — TCK-48210', at: '2026-07-20T08:47:00Z' },
  { id: 'ev-10', agentId: 'agt-3', type: 'call_started', description: 'Started follow-up call — TCK-48210', at: '2026-07-20T08:39:00Z' },

  { id: 'ev-11', agentId: 'agt-4', type: 'call_failed', description: 'Call failed to connect — TCK-47998', at: '2026-07-20T07:58:00Z' },
  { id: 'ev-12', agentId: 'agt-4', type: 'kb_query', description: 'Asked the KB assistant: "متى أحوّل المكالمة لموظف بشري؟"', at: '2026-07-20T07:52:00Z' },
  { id: 'ev-13', agentId: 'agt-4', type: 'call_started', description: 'Started follow-up call — TCK-47998', at: '2026-07-20T07:45:00Z' },
]
