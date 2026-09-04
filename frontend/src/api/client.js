import axios from 'axios'

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
 * Pull the human-readable reason out of a FastAPI error response.
 * The API surfaces `detail` as either a string or a list of validation errors;
 * we show what the server actually said rather than a generic failure message.
 */
export function describeApiError(error) {
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

export async function submitTrace({ address, maxHops }) {
  const { data } = await http.post('/api/trace', { address, max_hops: maxHops })
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
