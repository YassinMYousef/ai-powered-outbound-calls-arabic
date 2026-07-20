/**
 * Loads the unanswered-question (KB gap) log and resolves gaps
 * (backend/app/api/kb.py). Gaps are questions the RAG chatbot could not answer;
 * an admin reviews them, uploads the missing docs, then marks the group
 * resolved/dismissed. Switching the status filter reloads.
 */
import { useCallback, useEffect, useState } from 'react'
import { listGaps, resolveGap } from '../api/kb'
import { describeError } from '../api/client'
import type { GapStatus, KbGap } from '../types/kb'

export interface KbGapsState {
  gaps: KbGap[]
  status: GapStatus
  setStatus: (status: GapStatus) => void
  loading: boolean
  error: string | null
  reload: () => void
  resolve: (normalizedQuery: string, status: 'resolved' | 'dismissed', note?: string) => Promise<void>
  resolvingKey: string | null
}

export function useKbGaps(initialStatus: GapStatus = 'open'): KbGapsState {
  const [gaps, setGaps] = useState<KbGap[]>([])
  const [status, setStatus] = useState<GapStatus>(initialStatus)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [resolvingKey, setResolvingKey] = useState<string | null>(null)

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    listGaps(status)
      .then((rows) => {
        if (!cancelled) setGaps(rows)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describeError(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [status, attempt])

  const resolve = useCallback(
    async (normalizedQuery: string, nextStatus: 'resolved' | 'dismissed', note?: string) => {
      setResolvingKey(normalizedQuery)
      try {
        await resolveGap({ normalized_query: normalizedQuery, status: nextStatus, note })
        reload() // the group leaves the current (open) view
      } catch (err) {
        setError(describeError(err))
        throw err
      } finally {
        setResolvingKey(null)
      }
    },
    [reload],
  )

  return { gaps, status, setStatus, loading, error, reload, resolve, resolvingKey }
}
