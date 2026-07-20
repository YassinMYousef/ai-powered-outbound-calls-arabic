import { CheckCircle2, PhoneOutgoing, Timer } from 'lucide-react'
import StatCard from './StatCard'
import type { Kpis, Trends } from '../types/reports'
import { formatDuration, formatPercent } from '../utils/format'
import { FCR_TARGET, fcrStatus, trendDelta } from '../utils/kpi'

/** The 3 headline KPI cards, shared by OverviewPage and DetailsPage. */
export default function KpiStatCards({ kpis, trends }: { kpis: Kpis; trends: Trends }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <StatCard
        label="FCR rate"
        value={formatPercent(kpis.fcr_rate)}
        hint={`Target ≥ ${formatPercent(FCR_TARGET)}`}
        status={fcrStatus(kpis.fcr_rate)}
        icon={CheckCircle2}
        deltaFraction={trendDelta(trends.fcr)}
        deltaIsGoodWhenPositive
      />
      <StatCard
        label="AI call completion"
        value={formatPercent(kpis.completion_rate)}
        hint="Calls fully handled without human handoff"
        status="neutral"
        icon={PhoneOutgoing}
        deltaFraction={trendDelta(trends.completion)}
        deltaIsGoodWhenPositive
      />
      <StatCard
        label="Avg. handle time"
        value={formatDuration(kpis.average_handle_time)}
        hint="vs. live-agent baseline"
        status="neutral"
        icon={Timer}
        deltaFraction={trendDelta(trends.aht)}
        deltaIsGoodWhenPositive={false}
      />
    </div>
  )
}
