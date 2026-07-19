/**
 * Quality-manager view — KPIs from GET /api/reports/kpis (backend/app/api/reports.py).
 * Module: Frontend/Dashboard.
 *
 * Three sub-pages behind one AppShell: Overview (small insights — the 3 stat
 * cards), Details (the same cards for context, plus 14-day trend charts), and
 * Agent Activity (per-agent roster + activity feed, mock — see
 * data/mockAgentActivity.ts). Overview/Details still read from
 * data/mockReports.ts — Sprint 3 swaps that import for a real
 * `api<Kpis>('/api/reports/kpis')` call — see docs/frontend-dashboard.md.
 */
import { useState } from 'react'
import AppShell from '../components/layout/AppShell'
import OverviewPage from './OverviewPage'
import DetailsPage from './DetailsPage'
import AgentActivityPage from './AgentActivityPage'

type View = 'overview' | 'details' | 'agents'

export default function DashboardPage() {
  const [view, setView] = useState<View>('overview')

  return (
    <AppShell
      tabs={[
        { label: 'Overview', active: view === 'overview', onClick: () => setView('overview') },
        { label: 'Details', active: view === 'details', onClick: () => setView('details') },
        { label: 'Agent Activity', active: view === 'agents', onClick: () => setView('agents') },
      ]}
    >
      {view === 'overview' && <OverviewPage />}
      {view === 'details' && <DetailsPage />}
      {view === 'agents' && <AgentActivityPage />}
    </AppShell>
  )
}
