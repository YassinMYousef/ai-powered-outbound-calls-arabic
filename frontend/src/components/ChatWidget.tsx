/**
 * Embeddable Arabic chat widget for the agent desktop.
 * Module: Frontend/Dashboard; backend contract in backend/app/api/chat.py.
 *
 * Content is Arabic → keep dir="rtl". Answers must render their source
 * citations alongside the text.
 *
 * TODO: POST { query } to /api/chat/query via api() and render
 * { answer, sources }.
 */
import { useState } from 'react'

export default function ChatWidget() {
  const [query, setQuery] = useState('')

  return (
    <section dir="rtl" style={{ border: '1px solid #ccc', borderRadius: 8, padding: 16, marginTop: 24 }}>
      <h2>مساعد قاعدة المعرفة</h2>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="اكتب سؤالك هنا…"
        style={{ width: '100%', padding: 8, boxSizing: 'border-box' }}
      />
      <p style={{ color: '#888' }}>غير مفعّل بعد — بانتظار واجهة RAG</p>
    </section>
  )
}
