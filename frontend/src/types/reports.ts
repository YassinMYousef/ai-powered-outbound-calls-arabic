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

/** Mirrors GET /api/reports/trends — per-day KPI series, oldest first. */
export interface Trends {
  fcr: TrendPoint[]
  completion: TrendPoint[]
  aht: TrendPoint[]
}

/**
 * GET /api/reports/fcr — the auto-generated "First Call Resolutions" report.
 * Backend is a 501 stub (data/reporting.generate_fcr_report); this shape mirrors
 * data/models.py::FCRReport, the row the report is compiled from, and applies
 * once the endpoint lands.
 */
export interface FcrReport {
  id: number
  period_start: string // ISO 8601
  period_end: string // ISO 8601
  total_calls: number
  resolved_first_attempt: number
  fcr_rate: number | null // 0-1
  completion_rate: number | null // 0-1
  average_handle_time_seconds: number | null
  report_markdown: string | null // formatted Arabic article
  created_at: string | null
}
