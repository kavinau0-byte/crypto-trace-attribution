import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ChevronRight } from 'lucide-react'
import { describeApiError, listCases } from '../api/client'
import MonoValue from '../components/MonoValue'
import { ConfidenceMeter, RiskFlagCount, Skeleton, VaspTag } from '../components/Indicators'
import { formatDateTime, relativeTime } from '../lib/format'

export default function CaseHistory() {
  const [cases, setCases] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    listCases()
      .then((data) => {
        if (!cancelled) setCases(Array.isArray(data) ? data : [])
      })
      .catch((err) => {
        if (!cancelled) setError(describeApiError(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10">
      <header className="mb-7 flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">Cases</h1>
        {cases?.length ? (
          <span className="data text-[13px] tabular-nums text-ink-faint">
            {cases.length} traced
          </span>
        ) : null}
      </header>

      {error ? <ErrorState message={error} /> : null}
      {!error && cases === null ? <LoadingRows /> : null}
      {!error && cases?.length === 0 ? <EmptyState /> : null}
      {!error && cases?.length ? <CaseTable cases={cases} /> : null}
    </div>
  )
}

function CaseTable({ cases }) {
  return (
    <div className="overflow-x-auto rounded-md border border-line bg-surface">
      <table className="w-full min-w-[820px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line">
            {['Case', 'Query address', 'Matched VASP', 'Confidence', 'Risk signals', 'Traced', ''].map(
              (h, i) => (
                <th
                  key={h || i}
                  scope="col"
                  className="px-4 py-2.5 text-[12px] font-medium text-ink-faint"
                >
                  {h}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr
              key={c.id}
              className="group border-b border-line/60 transition-colors last:border-b-0 hover:bg-raised"
            >
              <td className="px-4 py-3">
                <span className="data text-[13px] tabular-nums text-ink-dim">#{c.id}</span>
              </td>
              <td className="max-w-[260px] px-4 py-3">
                <MonoValue value={c.query_address} head={12} tail={8} />
              </td>
              <td className="px-4 py-3">
                <VaspTag vasp={c.matched_vasp} />
              </td>
              <td className="px-4 py-3">
                <ConfidenceMeter value={c.confidence} />
              </td>
              <td className="px-4 py-3">
                <RiskFlagCount flags={c.risk_flags} />
              </td>
              <td className="px-4 py-3">
                <span className="text-[13px] text-ink-dim" title={formatDateTime(c.created_at)}>
                  {relativeTime(c.created_at)}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  to={`/cases/${c.id}`}
                  className="inline-flex items-center gap-1 text-[13px] font-medium text-ink-faint transition-colors group-hover:text-accent"
                >
                  Open
                  <ChevronRight size={14} strokeWidth={2} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="rounded-md border border-line bg-surface px-6 py-16 text-center">
      <h2 className="text-[15px] font-semibold text-ink">No cases yet</h2>
      <p className="mx-auto mt-2 max-w-sm text-[13px] leading-relaxed text-ink-dim">
        Every trace you run is saved here with its attribution result and hop trail.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex rounded-sm border border-white/10 bg-accent/75 px-4 py-2 text-[13px] font-semibold text-void backdrop-blur transition-[background-color,backdrop-filter] hover:bg-accent/90 hover:backdrop-blur-md active:bg-accent"
      >
        Trace an address
      </Link>
    </div>
  )
}

function ErrorState({ message }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-md border border-alert/35 bg-alert/10 px-4 py-3"
    >
      <AlertTriangle size={15} strokeWidth={2} className="mt-0.5 shrink-0 text-alert" />
      <p className="text-[13px] leading-relaxed text-ink">{message}</p>
    </div>
  )
}

function LoadingRows() {
  return (
    <div className="rounded-md border border-line bg-surface p-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 border-b border-line/60 py-3.5 last:border-b-0">
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-3 w-64" />
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-20" />
          <Skeleton className="ml-auto h-3 w-20" />
        </div>
      ))}
    </div>
  )
}
