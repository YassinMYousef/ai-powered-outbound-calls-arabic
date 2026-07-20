/**
 * Manager view of what each agent is doing — mock data (see
 * data/mockAgentActivity.ts for why: CallLog has no agent-identity column).
 */
import { useState } from 'react'
import {
  ArrowRightLeft,
  CheckCircle2,
  MessageCircleQuestion,
  PhoneCall,
  PhoneOff,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import type { ActivityEventType } from '../types/agentActivity'
import { mockActivity, mockAgents } from '../data/mockAgentActivity'
import { formatDateTime, formatPercent } from '../utils/format'

const EVENT_ICON: Record<ActivityEventType, typeof PhoneCall> = {
  call_started: PhoneCall,
  call_resolved: CheckCircle2,
  call_unresolved: PhoneOff,
  call_transferred: ArrowRightLeft,
  call_failed: XCircle,
  kb_query: MessageCircleQuestion,
}

const EVENT_TONE: Record<ActivityEventType, string> = {
  call_started: 'bg-[var(--brand)]/10 text-[var(--brand)]',
  call_resolved: 'bg-[var(--success)]/10 text-[var(--success)]',
  call_unresolved: 'bg-[var(--accent)]/10 text-[var(--accent)]',
  call_transferred: 'bg-[var(--accent)]/10 text-[var(--accent)]',
  call_failed: 'bg-[var(--danger)]/10 text-[var(--danger)]',
  kb_query: 'bg-[var(--surface-muted)] text-[var(--text-muted)]',
}

export default function AgentActivityPage() {
  const [selectedId, setSelectedId] = useState(mockAgents[0]?.id)
  const selectedAgent = mockAgents.find((a) => a.id === selectedId) ?? mockAgents[0]
  const feed = mockActivity
    .filter((event) => event.agentId === selectedAgent?.id)
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())

  return (
    <>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Agent Activity</h2>
        <p className="text-sm text-[var(--text-muted)]">Who's handling what, and what they've done today.</p>
      </div>

      <div className="mb-4 flex items-start gap-2 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10 px-3 py-2">
        <ShieldAlert size={15} className="mt-0.5 shrink-0 text-[var(--accent)]" />
        <p className="text-xs leading-snug text-[var(--text-primary)]">
          Mock roster and activity — the backend has no per-agent identity on calls yet
          (<code>CallLog</code> doesn't track who handled a call). This becomes real once that's added.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] shadow-sm lg:col-span-2">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs text-[var(--text-muted)]">
                <th className="px-4 py-3 font-medium">Agent</th>
                <th className="px-4 py-3 font-medium">Calls</th>
                <th className="px-4 py-3 font-medium">Resolved</th>
                <th className="px-4 py-3 font-medium">KB</th>
              </tr>
            </thead>
            <tbody>
              {mockAgents.map((agent) => (
                <tr
                  key={agent.id}
                  onClick={() => setSelectedId(agent.id)}
                  className={`cursor-pointer border-b border-[var(--border-subtle)] last:border-0 transition-colors ${
                    agent.id === selectedAgent?.id ? 'bg-[var(--brand)]/5' : 'hover:bg-[var(--surface-muted)]'
                  }`}
                >
                  <td className="px-4 py-3">
                    <p className="text-xs font-medium text-[var(--text-primary)]">{agent.name}</p>
                    <p className="text-[11px] text-[var(--text-muted)]">Active {formatDateTime(agent.lastActiveAt)}</p>
                  </td>
                  <td className="font-mono-num px-4 py-3 text-xs text-[var(--text-primary)]">{agent.callsHandled}</td>
                  <td className="font-mono-num px-4 py-3 text-xs text-[var(--text-primary)]">
                    {formatPercent(agent.resolvedCount / agent.callsHandled)}
                  </td>
                  <td className="font-mono-num px-4 py-3 text-xs text-[var(--text-primary)]">{agent.kbQueries}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5 shadow-sm lg:col-span-3">
          {selectedAgent && (
            <>
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">{selectedAgent.name}</h3>
                <p className="text-xs text-[var(--text-muted)]">{selectedAgent.email}</p>
              </div>

              <ul className="space-y-3">
                {feed.map((event) => {
                  const Icon = EVENT_ICON[event.type]
                  return (
                    <li key={event.id} className="flex items-start gap-3">
                      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${EVENT_TONE[event.type]}`}>
                        <Icon size={13} strokeWidth={2.25} />
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs text-[var(--text-primary)]">{event.description}</p>
                        <p className="text-[11px] text-[var(--text-muted)]">{formatDateTime(event.at)}</p>
                      </div>
                    </li>
                  )
                })}
                {feed.length === 0 && <p className="text-xs text-[var(--text-muted)]">No activity recorded yet.</p>}
              </ul>
            </>
          )}
        </div>
      </div>
    </>
  )
}
