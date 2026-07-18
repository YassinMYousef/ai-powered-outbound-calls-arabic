/**
 * Embeddable Arabic RAG chat widget for the agent desktop.
 * Module: Frontend/Dashboard; backend contract in backend/app/api/chat.py.
 *
 * Sprint 2 scope: UI built on mock data (data/mockChat.ts). Sprint 4 swaps
 * `mockAnswer()` for a real `POST /api/chat/query` call, once Person C's RAG
 * pipeline and Person D's OAuth2/RBAC are both live — see docs/frontend-dashboard.md.
 *
 * All UI chrome (labels, buttons, placeholders) is English. Arabic is reserved
 * for what the RAG model itself produces/consumes: the agent's typed query, the
 * generated answer, and literal cited quotes from Arabic KB documents.
 */
import { useState } from 'react'
import type { FormEvent } from 'react'
import { BookOpen, Loader2, Send, Sparkles } from 'lucide-react'
import type { ChatMessage } from '../types/chat'
import { mockAnswer, SUGGESTED_QUERIES } from '../data/mockChat'

let nextId = 0
const makeId = () => `msg-${++nextId}`

export default function ChatWidget() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)

  function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    setMessages((prev) => [...prev, { id: makeId(), role: 'agent', text: trimmed }])
    setQuery('')
    setIsLoading(true)

    // Mock latency so the loading state is visible — Sprint 4 replaces this with a real await.
    setTimeout(() => {
      const { answer, sources } = mockAnswer(trimmed)
      setMessages((prev) => [...prev, { id: makeId(), role: 'assistant', text: answer, sources }])
      setIsLoading(false)
    }, 500)
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    send(query)
  }

  return (
    <section className="flex h-[480px] flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] shadow-sm">
      <header className="flex items-center gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--brand)]/10 text-[var(--brand)]">
          <Sparkles size={16} strokeWidth={2.25} />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Knowledge Base Assistant</h2>
          <p className="text-xs text-[var(--text-muted)]">Cited Arabic Q&amp;A over the internal KB &middot; mock data</p>
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
                  onClick={() => send(suggestion)}
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
                dir="rtl"
                className={`font-arabic rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  message.role === 'agent'
                    ? 'rounded-tr-sm bg-[var(--brand)] text-white'
                    : 'rounded-tl-sm bg-[var(--surface-muted)] text-[var(--text-primary)]'
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
