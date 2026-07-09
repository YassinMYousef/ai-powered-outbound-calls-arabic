/**
 * FCR dashboard — KPIs from GET /api/reports/kpis (backend/app/api/reports.py).
 * Module: Frontend/Dashboard.
 *
 * TODO: fetch KPIs via api() and render charts (recharts is already a dependency):
 *   - FCR rate (target ≥ 90%)
 *   - AI call completion %
 *   - Average handle time vs live-agent baseline
 */
import ChatWidget from '../components/ChatWidget'

export default function DashboardPage() {
  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: 24, fontFamily: 'system-ui' }}>
      <h1>CallCenter Dashboard</h1>
      <p>KPIs pending — waiting on the reporting API (backend/app/api/reports.py):</p>
      <ul>
        <li>FCR rate</li>
        <li>AI call completion %</li>
        <li>Average handle time</li>
      </ul>
      <ChatWidget />
    </main>
  )
}
