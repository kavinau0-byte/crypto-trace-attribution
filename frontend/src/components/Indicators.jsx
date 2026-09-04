import { formatConfidence, matchMethodLabel, riskFlagLabel } from '../lib/format'

/**
 * Confidence reads as a bounded score, never as a percentage certainty about a
 * named entity. The bar is a magnitude cue; the number stays authoritative.
 */
export function ConfidenceMeter({ value, width = 'w-24', showValue = true }) {
  const n = Number(value)
  const safe = Number.isFinite(n) ? Math.min(Math.max(n, 0), 1) : 0
  const resolved = safe > 0

  return (
    <span className="inline-flex items-center gap-2.5" title={`Confidence score ${formatConfidence(value)} of 1.00`}>
      <span className={`relative h-1 ${width} overflow-hidden rounded-full bg-line`}>
        <span
          className={`absolute inset-y-0 left-0 rounded-full ${resolved ? 'bg-accent' : 'bg-line-strong'}`}
          style={{ width: `${Math.max(safe * 100, resolved ? 4 : 0)}%` }}
        />
      </span>
      {showValue ? (
        <span className="data text-[12px] tabular-nums text-ink-dim">{formatConfidence(value)}</span>
      ) : null}
    </span>
  )
}

/** Risk flags are heuristic signals, so they are labelled as signals. */
export function RiskFlags({ flags, empty = 'None raised' }) {
  const list = Array.isArray(flags) ? flags : []
  if (!list.length) {
    return <span className="text-[13px] text-ink-faint">{empty}</span>
  }
  return (
    <span className="flex flex-wrap gap-1.5">
      {list.map((flag) => (
        <span
          key={flag}
          className="inline-flex items-center rounded-sm border border-alert/35 bg-alert/10 px-2 py-0.5 text-[12px] font-medium text-alert"
        >
          {riskFlagLabel(flag)}
        </span>
      ))}
    </span>
  )
}

/** Compact count badge for the case table, where full pills would crowd the row. */
export function RiskFlagCount({ flags }) {
  const list = Array.isArray(flags) ? flags : []
  if (!list.length) return <span className="text-[13px] text-ink-faint">None</span>
  return (
    <span
      title={list.map(riskFlagLabel).join(', ')}
      className="inline-flex items-center gap-1.5 rounded-sm border border-alert/35 bg-alert/10 px-2 py-0.5 text-[12px] font-medium text-alert"
    >
      <span className="data tabular-nums">{list.length}</span>
      {list.length === 1 ? 'signal' : 'signals'}
    </span>
  )
}

/**
 * A VASP attribution outcome. Green marks a resolved match — an attribution
 * result, not a verdict about the address or its owner.
 */
export function VaspTag({ vasp, method }) {
  if (!vasp) {
    return (
      <span className="text-[13px] text-ink-faint">
        Unresolved
        {method && method !== 'unresolved' ? ` · ${matchMethodLabel(method)}` : ''}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-1.5 w-1.5 rounded-full bg-match" aria-hidden="true" />
      <span className="text-[13px] font-medium text-ink">{vasp}</span>
    </span>
  )
}

export function Panel({ title, action, children, className = '', bodyClassName = 'p-5' }) {
  return (
    <section className={`rounded-md border border-line bg-surface ${className}`}>
      {title ? (
        <header className="flex items-center justify-between gap-4 border-b border-line px-5 py-3">
          <h2 className="text-[13px] font-semibold tracking-tight text-ink-dim">{title}</h2>
          {action}
        </header>
      ) : null}
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}

/** Label/value pair used across the attribution summary. */
export function Field({ label, children, className = '' }) {
  return (
    <div className={className}>
      <dt className="mb-1.5 text-[12px] font-medium text-ink-faint">{label}</dt>
      <dd className="text-[14px] text-ink">{children}</dd>
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-sm bg-line ${className}`} />
}
