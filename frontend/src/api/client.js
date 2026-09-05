import axios, { isCancel } from 'axios'

// Never hardcode the host inline — the backend may be run on another port for a demo.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '')

// A trace walks the Bitcoin graph live against mempool.space, one HTTP request
// per address, with retry/backoff on the server side. Busy addresses at higher
// max_hops legitimately take minutes, so there is no short client timeout here —
// the UI reports elapsed time instead of pretending the request should be quick.
const http = axios.create({ baseURL: API_BASE_URL, timeout: 0 })

/**
 * Did this request fail because we deliberately aborted it?
 *
 * A cancelled request is not a failure and must never be shown as an error.
 * axios raises CanceledError (code ERR_CANCELED) when an AbortSignal fires;
 * the DOMException check covers a raw fetch/XHR abort reaching here by another
 * path, so callers can rely on this regardless of transport.
 */
export function isAbortError(error) {
  if (!error) return false
  return (
    isCancel(error) ||
    error.code === 'ERR_CANCELED' ||
    error.name === 'AbortError' ||
    error.name === 'CanceledError'
  )
}

/**
 * Pull the human-readable reason out of a FastAPI error response.
 * The API surfaces `detail` as either a string or a list of validation errors;
 * we show what the server actually said rather than a generic failure message.
 */
export function describeApiError(error) {
  // Callers should branch on isAbortError() first; this is a backstop so a
  // cancellation can never surface as a scary red failure message.
  if (isAbortError(error)) return 'Trace cancelled.'

  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const where = Array.isArray(d.loc) ? d.loc.filter((p) => p !== 'body').join('.') : ''
        return where ? `${where}: ${d.msg}` : d.msg
      })
      .filter(Boolean)
      .join('; ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)

  const status = error?.response?.status
  if (status) return `${status} ${error.response.statusText || 'error'} from ${API_BASE_URL}`
  if (error?.code === 'ERR_NETWORK') {
    return `Could not reach the backend at ${API_BASE_URL}. Start it with "uvicorn app.main:app --reload" from the backend directory.`
  }
  return error?.message || 'The request failed.'
}

export async function getHealth() {
  const { data } = await http.get('/api/health', { timeout: 5000 })
  return data
}

/**
 * `signal` lets the caller abandon a trace that is taking too long. It stops
 * THIS side waiting: the backend handler is a sync def running in FastAPI's
 * threadpool, so a dropped connection does not interrupt it — the trace runs
 * to completion server-side and the case is still committed, which is why the
 * UI tells the person to look in Cases rather than claiming it was undone.
 */
export async function submitTrace({ address, maxHops, signal }) {
  const { data } = await http.post(
    '/api/trace',
    { address, max_hops: maxHops },
    { signal }
  )
  return data
}

export async function listCases() {
  const { data } = await http.get('/api/cases', { timeout: 15000 })
  return data
}

export async function getCase(id) {
  const { data } = await http.get(`/api/cases/${id}`, { timeout: 15000 })
  return data
}

export function reportUrl(id) {
  return `${API_BASE_URL}/api/cases/${id}/report`
}
