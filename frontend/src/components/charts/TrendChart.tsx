import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TrendPoint } from '../../types/reports'
import { formatShortDate } from '../../utils/format'

interface TrendChartProps {
  title: string
  data: TrendPoint[]
  color: string
  valueFormatter: (value: number) => string
}

interface TooltipPayloadEntry {
  value: number
  payload: TrendPoint
}

function ChartTooltip({ active, payload, formatter }: { active?: boolean; payload?: TooltipPayloadEntry[]; formatter: (v: number) => string }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-[var(--text-primary)]">{formatShortDate(point.date)}</p>
      <p className="font-mono-num text-[var(--text-muted)]">{formatter(point.value)}</p>
    </div>
  )
}

export default function TrendChart({ title, data, color, valueFormatter }: TrendChartProps) {
  const gradientId = `trend-${title.replace(/\s+/g, '-').toLowerCase()}`

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
        <span className="text-xs text-[var(--text-muted)]">Last 14 days</span>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.28} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatShortDate}
            tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
            axisLine={false}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={40} />
          <Tooltip content={<ChartTooltip formatter={valueFormatter} />} />
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill={`url(#${gradientId})`} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
