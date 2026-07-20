/** Mirrors POST /api/chat/query's response shape (backend/app/conversation/rag/answer.py). */
export interface ChatSource {
  doc_id: number
  title: string
  source_uri: string | null
  chunk_index: number
  score: number
  quotes: string[]
}

export interface ChatResponse {
  /** Conversation id — resend it with follow-up questions to keep context. */
  session_id: number
  answer: string
  sources: ChatSource[]
}

export interface ChatMessage {
  id: string
  role: 'agent' | 'assistant'
  text: string
  sources?: ChatSource[]
  /** Widget-local: the request failed — `text` is an English error notice, not an answer. */
  error?: boolean
}
