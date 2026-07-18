/**
 * Mock RAG responses for the embeddable chat widget (Sprint 2, mock data).
 *
 * Sprint 4 replaces this module's call sites with a real
 * `api<ChatResponse>('/api/chat/query', { method: 'POST', body: ... })` call once
 * Person C's RAG pipeline and Person D's OAuth2/RBAC are both live (both land end
 * of Sprint 3) — see docs/frontend-dashboard.md and backend/app/api/chat.py's
 * TODO(auth) note.
 *
 * Only what the RAG model itself produces/consumes is Arabic: the agent's typed
 * query, the generated answer, and the literal cited quotes (verbatim spans of
 * Arabic KB text). Source titles and all other UI text stay English.
 */
import type { ChatResponse } from '../types/chat'

interface MockEntry {
  keywords: string[]
  response: ChatResponse
}

const NO_MATCH: ChatResponse = {
  answer: 'لا توجد معلومات عن هذا الموضوع في قاعدة المعرفة الداخلية.',
  sources: [],
}

const ENTRIES: MockEntry[] = [
  {
    keywords: ['كلمة المرور', 'كلمة مرور', 'باسورد'],
    response: {
      answer:
        'لإعادة تعيين كلمة مرور العميل، انتقل إلى لوحة إدارة الحسابات، ثم اختر "إعادة تعيين كلمة المرور" وأدخل رقم الهاتف المسجل. سيصل رمز تحقق مكوّن من ٦ أرقام عبر رسالة نصية صالح لمدة ١٠ دقائق.',
      sources: [
        {
          doc_id: 101,
          title: 'Customer Account Management Guide',
          source_uri: 'kb://account-management/password-reset',
          chunk_index: 3,
          score: 0.91,
          quotes: ['أدخل رقم الهاتف المسجل. سيصل رمز تحقق مكوّن من ٦ أرقام'],
        },
      ],
    },
  },
  {
    keywords: ['استرجاع', 'استرداد', 'الاسترجاع'],
    response: {
      answer:
        'سياسة الاسترجاع تسمح للعميل بطلب استرداد المبلغ خلال ١٤ يوماً من تاريخ الشراء، بشرط أن يكون المنتج غير مستخدم وبعبوته الأصلية. تتم معالجة الطلب خلال ٥ أيام عمل بعد استلام المنتج.',
      sources: [
        {
          doc_id: 204,
          title: 'Returns & Exchange Policy',
          source_uri: 'kb://policies/returns',
          chunk_index: 1,
          score: 0.88,
          quotes: ['يسمح للعميل بطلب استرداد المبلغ خلال ١٤ يوماً من تاريخ الشراء'],
        },
      ],
    },
  },
  {
    keywords: ['تحويل', 'موظف', 'وكيل بشري'],
    response: {
      answer:
        'يمكن تحويل المكالمة إلى موظف بشري عند طلب العميل ذلك صراحةً أو بعد فشل محاولتين للتعرف على نية العميل. استخدم زر "تحويل" في شاشة المكالمة الحالية لتوجيه المكالمة إلى قائمة انتظار الدعم.',
      sources: [
        {
          doc_id: 88,
          title: 'Human Escalation Procedure',
          source_uri: 'kb://call-flow/escalation',
          chunk_index: 2,
          score: 0.84,
          quotes: ['استخدم زر "تحويل" في شاشة المكالمة الحالية'],
        },
      ],
    },
  },
]

/** Keyword match over the mock KB, mirroring the shape (not the logic) of app/conversation/rag/answer.py. */
export function mockAnswer(queryAr: string): ChatResponse {
  const hit = ENTRIES.find((entry) => entry.keywords.some((kw) => queryAr.includes(kw)))
  return hit ? hit.response : NO_MATCH
}

export const SUGGESTED_QUERIES = ['كيف أعيد تعيين كلمة مرور العميل؟', 'ما هي سياسة الاسترجاع؟', 'متى أحوّل المكالمة لموظف بشري؟']
