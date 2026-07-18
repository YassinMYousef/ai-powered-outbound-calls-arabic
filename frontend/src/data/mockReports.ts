/**
 * Mock data for the KPI cards and trend charts.
 *
 * Sprint 2 scope (sprint_plan.md.pdf, Person E): charts built against mock data.
 * Sprint 3 replaces this module's call sites with `api<Kpis>('/api/reports/kpis')`
 * once backend/app/data/reporting.py is implemented (currently HTTP 501) — see
 * docs/frontend-dashboard.md.
 */
import type { Kpis, TrendPoint } from '../types/reports'

export const mockKpis: Kpis = {
  fcr_rate: 0.87,
  completion_rate: 0.74,
  average_handle_time: 142,
}

function buildTrend(base: number, drift: number, noise: number[], startDate = '2026-07-05'): TrendPoint[] {
  const start = new Date(startDate)
  return noise.map((n, i) => {
    const date = new Date(start)
    date.setDate(start.getDate() + i)
    return {
      date: date.toISOString().slice(0, 10),
      value: Math.round((base + drift * (i / noise.length) + n) * 1000) / 1000,
    }
  })
}

// 14-day trends, deterministic so the dashboard demos consistently.
export const mockFcrTrend: TrendPoint[] = buildTrend(
  0.79,
  0.08,
  [0, 0.01, -0.02, 0.015, 0.005, -0.01, 0.02, 0.01, 0.03, 0.0, 0.02, -0.005, 0.015, 0.01],
)

export const mockCompletionTrend: TrendPoint[] = buildTrend(
  0.68,
  0.06,
  [0, -0.01, 0.02, 0.0, 0.015, 0.01, -0.02, 0.03, 0.005, 0.02, -0.01, 0.015, 0.0, 0.01],
)

export const mockAhtTrend: TrendPoint[] = buildTrend(
  158,
  -16,
  [0, 3, -5, 2, -8, 4, -2, -6, 1, -4, 3, -3, -1, -2],
)
