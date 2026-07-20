/**
 * Embeddable Arabic RAG chat widget for the agent desktop.
 * Module: Frontend/Dashboard; backend contract in backend/app/api/chat.py.
 *
 * Queries POST /api/chat/query (Person C's RAG pipeline). The endpoint is still
 * unauthenticated — once Person D's OAuth2/RBAC lands, requests here carry the
 * bearer token from auth/AuthContext.
 *
 * All UI chrome (labels, buttons, placeholders, error notices) is English.
 * Arabic is reserved for what the RAG model itself produces/consumes: the
 * agent's typed query, the generated answer, and literal cited quotes.
 */
import { useState } from 'react'
import type { FormEvent } from 'react'
import { BookOpen, Loader2, Send, Sparkles } from 'lucide-react'
import { ApiError } from '../api/client'
import { sendChatQuery } from '../api/chat'
import type { ChatMessage } from '../types/chat'

const SUGGESTED_QUERIES = ['كيف أعيد تعيين كلمة مرور العميل؟', 'ما هي سياسة الاسترجاع؟', 'متى أحوّل المكالمة لموظف بشري؟']

let nextId = 0
const makeId = () => `msg-${++nextId}`

export default function ChatWidget() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  // Conversation id from the backend; deliberately useState (not sessionStorage) so a
  // page reload clears the visible transcript and the server-side context together.
  const [sessionId, setSessionId] = useState<number | null>(null)

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    setMessages((prev) => [...prev, { id: makeId(), role: 'agent', text: trimmed }])
    setQuery('')
    setIsLoading(true)

    try {
      const { session_id, answer, sources } = await sendChatQuery({
        query: trimmed,
        ...(sessionId !== null && { session_id: sessionId }),
      })
      setSessionId(session_id)
      setMessages((prev) => [...prev, { id: makeId(), role: 'assistant', text: answer, sources }])
    } catch (err) {
      // 404 = the server no longer knows this session; drop it so the next send starts fresh.
      const sessionExpired = err instanceof ApiError && err.status === 404
      if (sessionExpired) setSessionId(null)
      setMessages((prev) => [
        ...prev,
        {
          id: makeId(),
          role: 'assistant',
          error: true,
          text: sessionExpired
            ? 'انتهت هذه المحادثة. أعد إرسال سؤالك لبدء محادثة جديدة.'
            : 'The assistant is unavailable. Check that the backend is running and the answer service is configured, then try again.',
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    void send(query)
  }

  return (
    <section className="flex h-[480px] flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] shadow-sm">
      <header className="flex items-center gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--brand)]/10 text-[var(--brand)]">
          <Sparkles size={16} strokeWidth={2.25} />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Knowledge Base Assistant</h2>
          <p className="text-xs text-[var(--text-muted)]">Cited Arabic Q&amp;A over the internal KB</p>
        </div>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm text-[var(--text-muted)]">Ask a question in Arabic to see a cited answer.</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTED_QUERIES.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void send(suggestion)}
                  dir="rtl"
                  className="font-arabic rounded-full border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-3 py-1.5 text-sm text-[var(--text-primary)] transition-colors hover:border-[var(--brand)] hover:text-[var(--brand)]"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === 'agent' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] ${message.role === 'agent' ? '' : 'w-full'}`}>
              <p
                dir={message.error ? 'auto' : 'rtl'}
                className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  message.error
                    ? 'rounded-tl-sm border border-[var(--danger)]/30 bg-[var(--danger)]/5 text-[var(--text-primary)]'
                    : message.role === 'agent'
                      ? 'font-arabic rounded-tr-sm bg-[var(--brand)] text-white'
                      : 'font-arabic rounded-tl-sm bg-[var(--surface-muted)] text-[var(--text-primary)]'
                }`}
              >
                {message.text}
              </p>

              {message.sources && message.sources.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    <BookOpen size={12} /> Sources
                  </p>
                  {message.sources.map((source) => (
                    <div
                      key={`${source.doc_id}-${source.chunk_index}`}
                      className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2"
                    >
                      <p className="text-xs font-medium text-[var(--text-primary)]">{source.title}</p>
                      {source.quotes.map((quote, i) => (
                        <p key={i} dir="rtl" className="font-arabic mt-1 text-xs italic text-[var(--text-muted)]">
                          &ldquo;{quote}&rdquo;
                        </p>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Loader2 size={14} className="animate-spin" />
            Thinking…
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-[var(--border-subtle)] p-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type your question in Arabic…"
          dir="auto"
          className="font-arabic flex-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none placeholder:font-sans placeholder:text-[var(--text-muted)] focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/20"
        />
        <button
          type="submit"
          disabled={!query.trim() || isLoading}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--brand)] text-white transition-opacity disabled:opacity-40"
          aria-label="Send"
        >
          <Send size={16} />
        </button>
      </form>
    </section>
  )
}
