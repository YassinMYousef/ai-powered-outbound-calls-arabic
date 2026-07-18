import type { ComponentType } from 'react'
import { TrendingDown, TrendingUp } from 'lucide-react'

export type StatStatus = 'good' | 'warn' | 'bad' | 'neutral'

interface StatCardProps {
  label: string
  value: string
  hint: string
  status: StatStatus
  icon: ComponentType<{ size?: number; strokeWidth?: number }>
  /** Fractional change vs. the prior period, e.g. 0.023 for +2.3%. Omit if not available. */
  deltaFraction?: number
  deltaIsGoodWhenPositive?: boolean
}

const STATUS_STYLES: Record<StatStatus, { badge: string; icon: string }> = {
  good: { badge: 'bg-[var(--success)]/10 text-[var(--success)]', icon: 'bg-[var(--success)]/10 text-[var(--success)]' },
  warn: { badge: 'bg-[var(--accent)]/10 text-[var(--accent)]', icon: 'bg-[var(--accent)]/10 text-[var(--accent)]' },
  bad: { badge: 'bg-[var(--danger)]/10 text-[var(--danger)]', icon: 'bg-[var(--danger)]/10 text-[var(--danger)]' },
  neutral: {
    badge: 'bg-[var(--surface-muted)] text-[var(--text-muted)]',
    icon: 'bg-[var(--surface-muted)] text-[var(--text-muted)]',
  },
}

export default function StatCard({
  label,
  value,
  hint,
  status,
  icon: Icon,
  deltaFraction,
  deltaIsGoodWhenPositive = true,
}: StatCardProps) {
  const styles = STATUS_STYLES[status]
  const isPositive = (deltaFraction ?? 0) >= 0
  const deltaIsGood = isPositive === deltaIsGoodWhenPositive

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <span className="text-sm font-medium text-[var(--text-muted)]">{label}</span>
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${styles.icon}`}>
          <Icon size={16} strokeWidth={2.25} />
        </span>
      </div>

      <p className="font-mono-num mt-3 text-3xl font-semibold text-[var(--text-primary)]">{value}</p>

      <div className="mt-2 flex items-center gap-2">
        {deltaFraction !== undefined && (
          <span
            className={`inline-flex items-center gap-0.5 text-xs font-medium ${
              deltaIsGood ? 'text-[var(--success)]' : 'text-[var(--danger)]'
            }`}
          >
            {isPositive ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
            {Math.abs(deltaFraction * 100).toFixed(1)}%
          </span>
        )}
        <span className="text-xs text-[var(--text-muted)]">{hint}</span>
      </div>

      <span className={`mt-3 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${styles.badge}`}>
        {status === 'good' ? 'On target' : status === 'warn' ? 'Watch' : status === 'bad' ? 'Below target' : '—'}
      </span>
    </div>
  )
}
