import KpiStatCards from '../components/KpiStatCards'
import TrendChart from '../components/charts/TrendChart'
import type { Kpis, Trends } from '../types/reports'
import { formatDuration, formatPercent } from '../utils/format'

/** Detailed view: the same KPI cards for context, plus the 14-day trend charts. */
export default function DetailsPage({ kpis, trends }: { kpis: Kpis; trends: Trends }) {
  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Details</h2>
        <p className="text-sm text-[var(--text-muted)]">
          14-day trends behind each KPI, for the outbound follow-up product.
        </p>
      </div>

      <KpiStatCards kpis={kpis} trends={trends} />

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <TrendChart title="FCR rate" data={trends.fcr} color="var(--brand)" valueFormatter={formatPercent} />
        <TrendChart title="AI call completion" data={trends.completion} color="var(--success)" valueFormatter={formatPercent} />
        <TrendChart title="Avg. handle time" data={trends.aht} color="var(--accent)" valueFormatter={formatDuration} />
      </div>
    </>
  )
}
