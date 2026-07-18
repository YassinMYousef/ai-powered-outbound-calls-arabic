import { CheckCircle2, PhoneOutgoing, Timer } from 'lucide-react'
import StatCard from './StatCard'
import { mockAhtTrend, mockCompletionTrend, mockFcrTrend, mockKpis } from '../data/mockReports'
import { formatDuration, formatPercent } from '../utils/format'
import { FCR_TARGET, fcrStatus, trendDelta } from '../utils/kpi'

/** The 3 headline KPI cards, shared by OverviewPage and DetailsPage. */
export default function KpiStatCards() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <StatCard
        label="FCR rate"
        value={formatPercent(mockKpis.fcr_rate)}
        hint={`Target ≥ ${formatPercent(FCR_TARGET)}`}
        status={fcrStatus(mockKpis.fcr_rate)}
        icon={CheckCircle2}
        deltaFraction={trendDelta(mockFcrTrend)}
        deltaIsGoodWhenPositive
      />
      <StatCard
        label="AI call completion"
        value={formatPercent(mockKpis.completion_rate)}
        hint="Calls fully handled without human handoff"
        status="neutral"
        icon={PhoneOutgoing}
        deltaFraction={trendDelta(mockCompletionTrend)}
        deltaIsGoodWhenPositive
      />
      <StatCard
        label="Avg. handle time"
        value={formatDuration(mockKpis.average_handle_time)}
        hint="vs. live-agent baseline"
        status="neutral"
        icon={Timer}
        deltaFraction={trendDelta(mockAhtTrend)}
        deltaIsGoodWhenPositive={false}
      />
    </div>
  )
}
