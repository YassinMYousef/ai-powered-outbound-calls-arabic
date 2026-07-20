/** Knowledge-base document management — backend/app/api/kb.py. */
import { api } from './client'
import type { GapResolution, GapStatus, KbGap, KBDocument, KBUploadResult } from '../types/kb'

/** GET /api/kb/documents — all KB docs, newest first, with embedding status. */
export function listDocuments(): Promise<KBDocument[]> {
  return api<KBDocument[]>('/api/kb/documents')
}

/** POST /api/kb/documents — upload a txt/md/pdf/docx file and enqueue embedding.
 *  Throws ApiError 415 (unsupported type) or 400 (no extractable text). */
export function uploadDocument(file: File): Promise<KBUploadResult> {
  const form = new FormData()
  form.append('file', file)
  return api<KBUploadResult>('/api/kb/documents', { method: 'POST', body: form })
}

/** GET /api/kb/gaps — unanswered questions grouped by normalized text, most-hit
 *  first. `status` filters open (default) / resolved / dismissed. */
export function listGaps(status: GapStatus = 'open'): Promise<KbGap[]> {
  return api<KbGap[]>(`/api/kb/gaps?status=${status}`)
}

/** POST /api/kb/gaps/resolve — mark every open gap in a group resolved/dismissed.
 *  Returns how many rows changed. */
export function resolveGap(body: GapResolution): Promise<{ updated: number }> {
  return api<{ updated: number }>('/api/kb/gaps/resolve', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
