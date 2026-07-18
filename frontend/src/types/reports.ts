/** Mirrors GET /api/reports/kpis (backend/app/api/reports.py, backend/app/data/reporting.py). */
export interface Kpis {
  fcr_rate: number // 0-1, target >= 0.90
  completion_rate: number // 0-1, % of calls fully handled by the AI without human handoff
  average_handle_time: number // seconds
}

export interface TrendPoint {
  date: string // YYYY-MM-DD
  value: number
}
