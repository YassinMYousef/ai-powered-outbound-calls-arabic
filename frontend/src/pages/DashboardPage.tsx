/**
 * Quality-manager view — the four surfaces the backend exposes to this role:
 * Overview + Details (GET /api/reports/kpis + /trends), Knowledge Base
 * (GET/POST /api/kb/documents), and Operations (calls + FCR report).
 * Module: Frontend/Dashboard.
 *
 * Reports data is fetched once here (hooks/useReports.ts) and shared by the two
 * report sub-pages; KB and Operations own their own data fetching.
 */
import { useState } from 'react'
import { AlertTriangle, Loader2, RotateCw } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import OverviewPage from './OverviewPage'
import DetailsPage from './DetailsPage'
import KnowledgeBasePage from './KnowledgeBasePage'
import UnansweredQuestionsPage from './UnansweredQuestionsPage'
import OperationsPage from './OperationsPage'
import { useReports } from '../hooks/useReports'

type View = 'overview' | 'details' | 'kb' | 'gaps' | 'operations'

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
      ]}
    >
      {view === 'kb' && <KnowledgeBasePage />}
      {view === 'gaps' && <UnansweredQuestionsPage />}
      {view === 'operations' && <OperationsPage />}

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
