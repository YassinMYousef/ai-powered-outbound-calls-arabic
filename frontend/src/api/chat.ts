/** Agent-facing RAG chat endpoint — backend/app/api/chat.py. */
import { api } from './client'
import type { ChatResponse } from '../types/chat'

export interface ChatQueryBody {
  query: string // Arabic question
  top_k?: number // passages to ground the answer in (1-20); backend default when omitted
  session_id?: number // omit to start a new conversation
}

/** POST /api/chat/query — returns a cited Arabic answer. A 404 (ApiError.status)
 *  means the session_id is unknown/ended and the client should start fresh. */
export function sendChatQuery(body: ChatQueryBody): Promise<ChatResponse> {
  return api<ChatResponse>('/api/chat/query', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
