/**
 * Knowledge-base management — upload source documents and watch them embed.
 * Wires GET + POST /api/kb/documents (backend/app/api/kb.py); the RAG ChatWidget
 * answers only over what is embedded here.
 *
 * Quality-manager surface: KB content is proprietary, so this sits behind the
 * dashboard rather than the agent console.
 */
import { useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { AlertTriangle, CheckCircle2, FileText, Loader2, RotateCw, Upload } from 'lucide-react'
import { useKbDocuments } from '../hooks/useKbDocuments'
import { formatDateTime } from '../utils/format'

const ACCEPT = '.txt,.md,.pdf,.docx'

export default function KnowledgeBasePage() {
  const { documents, loading, error, uploading, uploadError, reload, upload } = useKbDocuments()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    // Upload sequentially so one failure doesn't abort the rest, and the list
    // reflects each as it lands.
    for (const file of Array.from(files)) {
      try {
        await upload(file)
      } catch {
        // uploadError is surfaced by the hook; keep going with the next file.
      }
    }
    if (inputRef.current) inputRef.current.value = ''
  }

  function onDrop(e: DragEvent<HTMLElement>) {
    e.preventDefault()
    setDragging(false)
    void handleFiles(e.dataTransfer.files)
  }

  function onInputChange(e: ChangeEvent<HTMLInputElement>) {
    void handleFiles(e.target.files)
  }

  const pending = documents.filter((d) => d.embedded_at === null).length

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Knowledge Base</h2>
          <p className="text-sm text-[var(--text-muted)]">
            Upload documents the assistant answers from. Embedding runs in the background — new files show as
            pending until indexed.
          </p>
        </div>
        <button
          type="button"
          onClick={reload}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--brand)]"
        >
          <RotateCw size={13} />
          Refresh
        </button>
      </div>

      {/* Upload dropzone */}
      <section
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging
            ? 'border-[var(--brand)] bg-[var(--brand)]/5'
            : 'border-[var(--border-subtle)] bg-[var(--surface-card)]'
        }`}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[var(--brand)]/10 text-[var(--brand)]">
          {uploading ? <Loader2 size={20} className="animate-spin" /> : <Upload size={20} />}
        </span>
        <div>
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {uploading ? 'Uploading…' : 'Drag & drop files, or'}{' '}
            {!uploading && (
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="font-medium text-[var(--brand)] underline-offset-2 hover:underline"
              >
                browse
              </button>
            )}
          </p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">TXT, Markdown, PDF, or DOCX</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          onChange={onInputChange}
          className="hidden"
        />
      </section>

      {uploadError && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/5 px-3 py-2">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[var(--danger)]" />
          <p className="text-xs text-[var(--text-primary)]">{uploadError}</p>
        </div>
      )}

      {/* Document list */}
      <div className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Documents {documents.length > 0 && <span className="text-[var(--text-muted)]">({documents.length})</span>}
          </h3>
          {pending > 0 && (
            <span className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
              <Loader2 size={12} className="animate-spin" />
              {pending} embedding…
            </span>
          )}
        </div>

        {loading && documents.length === 0 && (
          <div className="flex items-center gap-2 py-8 text-sm text-[var(--text-muted)]">
            <Loader2 size={16} className="animate-spin" />
            Loading documents…
          </div>
        )}

        {!loading && error && (
          <div className="flex items-start gap-3 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/5 p-4">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[var(--danger)]" />
            <div className="flex-1">
              <p className="text-sm font-medium text-[var(--text-primary)]">Could not load documents</p>
              <p className="mt-0.5 text-xs text-[var(--text-muted)]">{error}</p>
            </div>
            <button
              type="button"
              onClick={reload}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--brand)]"
            >
              <RotateCw size={13} />
              Retry
            </button>
          </div>
        )}

        {!error && !loading && documents.length === 0 && (
          <p className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] px-4 py-8 text-center text-sm text-[var(--text-muted)]">
            No documents yet. Upload a file above to build the knowledge base.
          </p>
        )}

        {documents.length > 0 && (
          <ul className="divide-y divide-[var(--border-subtle)] overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)]">
            {documents.map((doc) => {
              const embedded = doc.embedded_at !== null
              return (
                <li key={doc.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-muted)] text-[var(--text-muted)]">
                    <FileText size={16} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-[var(--text-primary)]">{doc.title}</p>
                    <p className="truncate text-xs text-[var(--text-muted)]">
                      Added {formatDateTime(doc.created_at)}
                      {doc.source_uri ? ` · ${doc.source_uri}` : ''}
                    </p>
                  </div>
                  {embedded ? (
                    <span
                      className="flex shrink-0 items-center gap-1 rounded-full bg-[var(--success)]/10 px-2.5 py-1 text-xs font-medium text-[var(--success)]"
                      title={`Embedded ${formatDateTime(doc.embedded_at)}`}
                    >
                      <CheckCircle2 size={12} />
                      Indexed
                    </span>
                  ) : (
                    <span className="flex shrink-0 items-center gap-1 rounded-full bg-[var(--accent)]/10 px-2.5 py-1 text-xs font-medium text-[var(--accent)]">
                      <Loader2 size={12} className="animate-spin" />
                      Pending
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </>
  )
}
