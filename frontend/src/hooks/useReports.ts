/**
 * Fetches the dashboard's reporting data (KPIs + 14-day trends) from the
 * backend. Fetched once per DashboardPage mount and shared by both sub-pages,
 * so switching Overview ↔ Details does not re-query.
 */
import { useCallback, useEffect, useState } from 'react'
import { getKpis, getTrends } from '../api/reports'
import type { Kpis, Trends } from '../types/reports'

export interface ReportsState {
  kpis: Kpis | null
  trends: Trends | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useReports(): ReportsState {
  const [kpis, setKpis] = useState<Kpis | null>(null)
  const [trends, setTrends] = useState<Trends | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([getKpis(), getTrends(14)])
      .then(([kpisData, trendsData]) => {
        if (cancelled) return
        setKpis(kpisData)
        setTrends(trendsData)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load reports')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [attempt])

  return { kpis, trends, loading, error, reload }
}
