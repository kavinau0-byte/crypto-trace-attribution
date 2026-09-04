/** Presentation helpers. Nothing here validates or re-derives engine logic. */

export const MATCH_METHOD_LABELS = {
  direct_tag: 'Direct Address Match',
  cluster_match: 'Cluster-Based Match',
  unresolved: 'No VASP Match',
}

export function matchMethodLabel(method) {
  return MATCH_METHOD_LABELS[method] || method || 'Unknown'
}

export function riskFlagLabel(flag) {
  return String(flag)
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/** Middle-truncate a hash or address, keeping both ends readable. */
export function truncateMiddle(value, head = 10, tail = 8) {
  const s = String(value ?? '')
  if (s.length <= head + tail + 1) return s
  return `${s.slice(0, head)}…${s.slice(-tail)}`
}

/** BTC amounts always show 8 dp — investigators compare them column-aligned. */
export function formatBtc(amount) {
  const n = Number(amount)
  if (!Number.isFinite(n)) return '—'
  return n.toFixed(8)
}

export function formatConfidence(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toFixed(2)
}

const RELATIVE_UNITS = [
  ['year', 31536000],
  ['month', 2592000],
  ['week', 604800],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]

/**
 * "2 hours ago". The API sends naive ISO strings from the server clock; a
 * missing timezone is read as UTC so relative times don't drift by the
 * viewer's offset.
 */
export function relativeTime(iso, now = Date.now()) {
  const parsed = parseTimestamp(iso)
  if (parsed === null) return '—'
  const seconds = Math.round((now - parsed) / 1000)
  if (seconds < 45) return 'just now'
  for (const [unit, size] of RELATIVE_UNITS) {
    if (Math.abs(seconds) >= size) {
      const n = Math.round(seconds / size)
      return `${n} ${unit}${n === 1 ? '' : 's'} ago`
    }
  }
  return 'just now'
}

export function parseTimestamp(iso) {
  if (!iso) return null
  let s = String(iso)
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(s)
  if (!hasZone) s = `${s}Z`
  const t = Date.parse(s)
  return Number.isNaN(t) ? null : t
}

/** Absolute UTC stamp for hop rows, where exact ordering matters. */
export function formatTimestamp(iso) {
  const t = parseTimestamp(iso)
  if (t === null) return 'Unconfirmed'
  return new Date(t).toISOString().replace('T', ' ').replace('.000Z', ' UTC')
}

export function formatDateTime(iso) {
  const t = parseTimestamp(iso)
  if (t === null) return '—'
  return new Date(t).toISOString().replace('T', ' ').slice(0, 16) + ' UTC'
}
