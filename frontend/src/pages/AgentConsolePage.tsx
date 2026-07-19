/**
 * Agent-facing view: two tabs behind one AppShell — the Knowledge Base
 * Assistant and the (simulated) call queue. Split out from DashboardPage so
 * role-gating (agent vs quality_manager) maps to a whole page — see App.tsx.
 */
import { useState } from 'react'
import AppShell from '../components/layout/AppShell'
import ChatWidget from '../components/ChatWidget'
import CallQueuePage from './CallQueuePage'

type View = 'assistant' | 'queue'

export default function AgentConsolePage() {
  const [view, setView] = useState<View>('assistant')

  return (
    <AppShell
      tabs={[
        { label: 'Assistant', active: view === 'assistant', onClick: () => setView('assistant') },
        { label: 'Call Queue', active: view === 'queue', onClick: () => setView('queue') },
      ]}
    >
      {view === 'assistant' ? (
        <>
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Knowledge Base Assistant</h2>
            <p className="text-sm text-[var(--text-muted)]">Cited Arabic Q&amp;A over the internal knowledge base.</p>
          </div>
          <ChatWidget />
        </>
      ) : (
        <CallQueuePage />
      )}
    </AppShell>
  )
}
