/**
 * Low-level fetch wrapper for the backend API. In dev the Vite server proxies
 * `/api/*` → http://localhost:8000 (see vite.config.ts), so every caller passes
 * a path starting with `/api` and relies on same-origin in production.
 *
 * This is the single choke point every typed api module flows through, so auth
 * (setAuthToken) and error normalisation (ApiError) live here — nowhere else.
 */

/** A non-2xx response. `status` lets callers branch (404 = gone, 501 = not built
 *  yet, 415 = bad upload) instead of string-matching the message. The message is
 *  kept as `API <status>: <body>` for readability in logs and error boxes. */
export class ApiError extends Error {
  readonly status: number
  readonly body: string

  constructor(status: number, body: string) {
    super(`API ${status}: ${body}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

// Bearer token for authenticated requests. Set by api/auth.ts after a successful
// POST /api/auth/token (and on session restore); null when signed out. Every
// reports/chat/kb/calls request flows through api() below, so this one line
// authenticates all of them.
let authToken: string | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  // Let the browser set the multipart boundary itself for FormData uploads;
  // forcing application/json there would corrupt the request.
  const isFormData = typeof FormData !== 'undefined' && init?.body instanceof FormData
  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`)

  const res = await fetch(path, { ...init, headers })
  if (!res.ok) throw new ApiError(res.status, await res.text())
  // 202/204 (accepted / no content) may carry no JSON body.
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

/** Human-readable one-liner for an error thrown by api(), for error notices. */
export function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 501) return 'This feature isn’t available yet — the backend endpoint is not implemented.'
    if (err.status === 503) return 'The service is not configured. Check the backend is running and provider keys are set.'
    if (err.status >= 500) return 'The server hit an error. Try again in a moment.'
    return err.body || err.message
  }
  return err instanceof Error ? err.message : 'Unexpected error'
}
