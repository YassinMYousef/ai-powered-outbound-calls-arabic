/** Reporting endpoints — backend/app/api/reports.py. */
import { api } from './client'
import type { FcrReport, Kpis, Trends } from '../types/reports'

/** GET /api/reports/kpis — headline FCR / completion / AHT figures. */
export function getKpis(): Promise<Kpis> {
  return api<Kpis>('/api/reports/kpis')
}

/** GET /api/reports/trends — per-day KPI series for the trend charts. */
export function getTrends(days = 14): Promise<Trends> {
  return api<Trends>(`/api/reports/trends?days=${days}`)
}

/** GET /api/reports/fcr — the generated "First Call Resolutions" report.
 *  Backend stub returns 501 until data/reporting.generate_fcr_report lands. */
export function getFcrReport(): Promise<FcrReport> {
  return api<FcrReport>('/api/reports/fcr')
}
