import KpiStatCards from '../components/KpiStatCards'

/** Small-insights view: the 3 headline KPI cards, nothing else — a quick glance for the quality team. */
export default function OverviewPage() {
  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Overview</h2>
        <p className="text-sm text-[var(--text-muted)]">
          A quick glance at First Call Resolution and call-handling KPIs. See Details for trends.
        </p>
      </div>
      <KpiStatCards />
    </>
  )
}
