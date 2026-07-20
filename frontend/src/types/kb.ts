/** Knowledge-base document shapes (backend/app/api/kb.py). */

/** One row from GET /api/kb/documents. `embedded_at` null ⇒ not yet embedded
 *  (the RAG ingest worker hasn't processed it) — the KB-coverage signal. */
export interface KBDocument {
  id: number
  title: string
  source_uri: string | null
  embedded_at: string | null // ISO 8601
  created_at: string | null // ISO 8601
}

/** POST /api/kb/documents response (HTTP 202). `status` is "pending_embedding". */
export interface KBUploadResult {
  id: number
  title: string
  status: string
}

/** Why the KB could not answer a question (backend/app/conversation/rag/answer.py):
 *  no_match — nothing retrieved; no_citation — passages retrieved but the grounded
 *  model cited none; low_confidence — cited, but the best passage was off-topic. */
export type GapReason = 'no_match' | 'no_citation' | 'low_confidence'

export type GapStatus = 'open' | 'resolved' | 'dismissed'

/** One row from GET /api/kb/gaps — unanswered questions grouped by normalized text.
 *  `normalized_query` is the group key POST /api/kb/gaps/resolve takes back. */
export interface KbGap {
  normalized_query: string
  sample_query: string // most recent original Arabic wording
  count: number // how many times this gap was hit
  reason: GapReason // the group's most common verdict
  reasons: Partial<Record<GapReason, number>> // full breakdown
  top_similarity: number | null // best passage's cosine (0-1), null when nothing cited
  first_seen: string | null // ISO 8601
  last_seen: string | null // ISO 8601
}

/** Body for POST /api/kb/gaps/resolve — mark a gap group done. */
export interface GapResolution {
  normalized_query: string
  status: 'resolved' | 'dismissed'
  note?: string
}
