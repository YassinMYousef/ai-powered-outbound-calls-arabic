import type { StatStatus } from '../components/StatCard'

export const FCR_TARGET = 0.9

export function fcrStatus(rate: number): StatStatus {
  if (rate >= FCR_TARGET) return 'good'
  if (rate >= 0.8) return 'warn'
  return 'bad'
}

export function trendDelta(trend: { value: number }[]): number {
  const first = trend[0]?.value ?? 0
  const last = trend[trend.length - 1]?.value ?? 0
  return first === 0 ? 0 : (last - first) / (Math.abs(first) < 1 ? 1 : first)
}
