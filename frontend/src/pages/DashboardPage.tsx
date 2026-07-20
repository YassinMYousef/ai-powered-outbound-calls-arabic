/**
 * Quality-manager view — every surface the dashboard exposes to this role,
 * behind one AppShell. Module: Frontend/Dashboard.
 *
 * Live, backed by real endpoints:
 *  - Overview + Details — GET /api/reports/kpis + /trends (fetched once via
 *    hooks/useReports and shared by both report sub-pages).
 *  - Knowledge Base — GET/POST /api/kb/documents.
 *  - Unanswered — GET/POST /api/kb/gaps (questions the RAG bot could not answer).
 *  - Operations — schedule a call batch + generate the FCR report.
 *  - Customers — real CRM records (backend/app/api/customers.py).
 *  - Agents — real agent roster (backend/app/api/agents.py).
 * Still mock:
 *  - Agent Activity — per-agent roster + activity feed; no backend to fetch yet
 *    (see docs/frontend-dashboard.md for why).
 */
import { useState } from 'react'
import { AlertTriangle, Loader2, RotateCw } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import OverviewPage from './OverviewPage'
import DetailsPage from './DetailsPage'
import KnowledgeBasePage from './KnowledgeBasePage'
import UnansweredQuestionsPage from './UnansweredQuestionsPage'
import OperationsPage from './OperationsPage'
import AgentActivityPage from './AgentActivityPage'
import CustomersPage from './CustomersPage'
import AgentsPage from './AgentsPage'
import { useReports } from '../hooks/useReports'

type View =
  | 'overview'
  | 'details'
  | 'kb'
  | 'gaps'
  | 'operations'
  | 'agent-activity'
  | 'customers'
  | 'agents'

export default function DashboardPage() {
  const [view, setView] = useState<View>('overview')
  const { kpis, trends, loading, error, reload } = useReports()

  const showReports = view === 'overview' || view === 'details'

  return (
    <AppShell
      tabs={[
        { label: 'Overview', active: view === 'overview', onClick: () => setView('overview') },
        { label: 'Details', active: view === 'details', onClick: () => setView('details') },
        { label: 'Knowledge Base', active: view === 'kb', onClick: () => setView('kb') },
        { label: 'Unanswered', active: view === 'gaps', onClick: () => setView('gaps') },
        { label: 'Operations', active: view === 'operations', onClick: () => setView('operations') },
        { label: 'Agent Activity', active: view === 'agent-activity', onClick: () => setView('agent-activity') },
        { label: 'Customers', active: view === 'customers', onClick: () => setView('customers') },
        { label: 'Agents', active: view === 'agents', onClick: () => setView('agents') },
      ]}
    >
      {view === 'kb' && <KnowledgeBasePage />}
      {view === 'gaps' && <UnansweredQuestionsPage />}
      {view === 'operations' && <OperationsPage />}
      {view === 'agent-activity' && <AgentActivityPage />}
      {view === 'customers' && <CustomersPage />}
      {view === 'agents' && <AgentsPage />}

      {showReports && loading && (
        <div className="flex items-center gap-2 py-12 text-sm text-[var(--text-muted)]">
          <Loader2 size={16} className="animate-spin" />
          Loading reports…
        </div>
      )}

      {showReports && !loading && error && (
        <div className="flex items-start gap-3 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/5 p-4">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[var(--danger)]" />
          <div className="flex-1">
            <p className="text-sm font-medium text-[var(--text-primary)]">Could not load reports</p>
            <p className="mt-0.5 text-xs text-[var(--text-muted)]">
              {error} — is the backend running on :8000 with the database up?
            </p>
          </div>
          <button
            type="button"
            onClick={reload}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--brand)]"
          >
            <RotateCw size={13} />
            Retry
          </button>
        </div>
      )}

      {showReports && !loading && !error && kpis && trends && (
        view === 'overview' ? (
          <OverviewPage kpis={kpis} trends={trends} />
        ) : (
          <DetailsPage kpis={kpis} trends={trends} />
        )
      )}
    </AppShell>
  )
}
