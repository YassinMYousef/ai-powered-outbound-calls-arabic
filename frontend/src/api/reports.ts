/** Reporting endpoints — backend/app/api/reports.py. */
import { api, apiBlob } from './client'
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

/** GET /api/reports/fcr.pdf — the branded report PDF; triggers a browser download. */
export async function downloadFcrReportPdf(days = 7): Promise<void> {
  const blob = await apiBlob(`/api/reports/fcr.pdf?days=${days}`)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `fcr-report-last-${days}-days.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
