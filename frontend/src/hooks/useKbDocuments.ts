/**
 * Loads the knowledge-base document list and handles uploads
 * (backend/app/api/kb.py). Embedding runs asynchronously in a Celery worker, so
 * a freshly uploaded doc lands with embedded_at=null; this hook polls the list
 * while any doc is still un-embedded and stops once they all have a timestamp.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { listDocuments, uploadDocument } from '../api/kb'
import { describeError } from '../api/client'
import type { KBDocument } from '../types/kb'

const POLL_INTERVAL_MS = 5000

export interface KbDocumentsState {
  documents: KBDocument[]
  loading: boolean
  error: string | null
  uploading: boolean
  uploadError: string | null
  reload: () => void
  upload: (file: File) => Promise<void>
}

export function useKbDocuments(): KbDocumentsState {
  const [documents, setDocuments] = useState<KBDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  useEffect(() => {
    let cancelled = false
    // Don't flip the whole list into a spinner on background poll refreshes —
    // only the first load shows "loading".
    if (attempt === 0) setLoading(true)

    listDocuments()
      .then((docs) => {
        if (cancelled) return
        setDocuments(docs)
        setError(null)
        // Reschedule a poll only while something is still embedding.
        if (docs.some((d) => d.embedded_at === null)) {
          timer.current = setTimeout(reload, POLL_INTERVAL_MS)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describeError(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
      if (timer.current) clearTimeout(timer.current)
    }
  }, [attempt, reload])

  const upload = useCallback(
    async (file: File) => {
      setUploading(true)
      setUploadError(null)
      try {
        await uploadDocument(file)
        reload() // show the new doc (pending) immediately; polling tracks embedding
      } catch (err) {
        setUploadError(describeError(err))
        throw err
      } finally {
        setUploading(false)
      }
    },
    [reload],
  )

  return { documents, loading, error, uploading, uploadError, reload, upload }
}
