/**
 * Agent-facing view: the Knowledge Base Assistant only. Split out from
 * DashboardPage so role-gating (agent vs quality_manager) maps to a whole
 * page rather than a section — see App.tsx.
 */
import AppShell from '../components/layout/AppShell'
import ChatWidget from '../components/ChatWidget'

export default function AgentConsolePage() {
  return (
    <AppShell>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Knowledge Base Assistant</h2>
        <p className="text-sm text-[var(--text-muted)]">Cited Arabic Q&amp;A over the internal knowledge base.</p>
      </div>
      <ChatWidget />
    </AppShell>
  )
}
