import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, Download, ExternalLink, Info } from 'lucide-react'
import { describeApiError, getCase, reportUrl } from '../api/client'
import MonoValue from '../components/MonoValue'
import CopyButton from '../components/CopyButton'

// three.js is the bulk of the bundle and is only needed once a trace with hops
// is on screen, so it loads with this panel rather than with the app.
const TraceGraph = lazy(() => import('../components/TraceGraph'))
import { ConfidenceMeter, Field, Panel, RiskFlags, Skeleton } from '../components/Indicators'
import { buildTraceGraph, NODE_KIND } from '../lib/graph'
import { formatBtc, formatDateTime, formatTimestamp, matchMethodLabel, relativeTime } from '../lib/format'

const EXPLORER_TX = 'https://mempool.space/tx/'

export default function CaseDetail() {
  const { id } = useParams()
  const location = useLocation()
  // A freshly submitted trace hands its result over directly, so the detail
  // view renders immediately instead of refetching what we already have.
  const [record, setRecord] = useState(() => location.state?.case ?? null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (record && String(record.id) === String(id)) return undefined
    let cancelled = false
    setRecord(null)
    setError(null)
    getCase(id)
      .then((data) => {
        if (!cancelled) setRecord(data)
      })
      .catch((err) => {
        if (!cancelled) setError(describeApiError(err))
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (error) {
    return (
      <div className="mx-auto w-full max-w-6xl px-6 py-10">
        <BackLink />
        <div
          role="alert"
          className="mt-6 flex items-start gap-2.5 rounded-md border border-alert/35 bg-alert/10 px-4 py-3"
        >
          <AlertTriangle size={15} strokeWidth={2} className="mt-0.5 shrink-0 text-alert" />
          <p className="text-[13px] leading-relaxed text-ink">{error}</p>
        </div>
      </div>
    )
  }

  if (!record) return <DetailSkeleton />

  return <CaseView record={record} />
}

function CaseView({ record }) {
  const trace = record.trace || {}
  const hops = Array.isArray(trace.hops) ? trace.hops : []
  const matched = Boolean(trace.matched_vasp)
  const graph = useMemo(() => buildTraceGraph(trace), [trace])
  const [selected, setSelected] = useState(null)

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10">
      <BackLink />

      <header className="mt-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-baseline gap-3">
            <h1 className="text-[22px] font-semibold tracking-tight text-ink">
              Investigative trace result
            </h1>
            <span className="data text-[13px] tabular-nums text-ink-faint">case #{record.id}</span>
          </div>
          <div className="mt-2 flex min-w-0 items-center gap-2">
            <span className="data truncate text-[14px] text-accent" title={trace.query_address}>
              {trace.query_address}
            </span>
            <CopyButton value={trace.query_address} label="Copy query address" />
          </div>
          <p className="mt-1.5 text-[12px] text-ink-faint" title={formatDateTime(record.created_at)}>
            Traced {relativeTime(record.created_at)} · {trace.chain || 'bitcoin'}
          </p>
        </div>

        <a
          href={reportUrl(record.id)}
          download
          className="inline-flex shrink-0 items-center gap-2 rounded-sm border border-line-strong px-3.5 py-2 text-[13px] font-medium text-ink transition-colors hover:border-accent hover:text-accent"
        >
          <Download size={14} strokeWidth={2} />
          Download PDF report
        </a>
      </header>

      <Panel title="Attribution" className="mt-7">
        <dl className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Matched VASP">
            {matched ? (
              <span className="inline-flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-match" aria-hidden="true" />
                <span className="font-medium">{trace.matched_vasp}</span>
              </span>
            ) : (
              <span className="text-ink-faint">No match in the seed list</span>
            )}
          </Field>
          <Field label="Confidence">
            <ConfidenceMeter value={trace.confidence} width="w-28" />
          </Field>
          <Field label="Match method">{matchMethodLabel(trace.match_method)}</Field>
          <Field label="Risk signals">
            <RiskFlags flags={record.risk_flags} />
          </Field>
        </dl>

        <p className="mt-6 border-t border-line pt-4 text-[12px] leading-relaxed text-ink-faint">
          Attribution is checked against a curated seed list of publicly documented
          exchange addresses and the query address&apos;s co-spend cluster, so coverage is
          partial by design. A match indicates a likely service relationship to
          investigate — it is not an identification of any person or an indication of
          wrongdoing.
        </p>
      </Panel>

      <Panel
        title="Fund flow"
        className="mt-6"
        bodyClassName=""
        action={
          hops.length ? (
            <span className="data text-[12px] tabular-nums text-ink-faint">
              {graph.addressCount} addresses · {hops.length} hops
            </span>
          ) : null
        }
      >
        {hops.length === 0 ? (
          <NoOutgoingFlow />
        ) : (
          <div className="grid lg:grid-cols-[1fr_280px]">
            <div className="h-[440px] border-b border-line lg:h-[560px] lg:border-b-0">
              <Suspense fallback={<GraphLoading />}>
                <TraceGraph
                  graph={graph}
                  matched={matched}
                  selectedId={selected?.id}
                  onSelect={setSelected}
                />
              </Suspense>
            </div>
            <NodeInspector node={selected} matched={matched} vasp={trace.matched_vasp} />
          </div>
        )}
      </Panel>

      {graph.hasUnknownPayer ? <PayerNotice /> : null}

      {hops.length ? <HopLedger hops={hops} /> : null}
    </div>
  )
}

function BackLink() {
  return (
    <Link
      to="/cases"
      className="inline-flex items-center gap-1.5 text-[13px] text-ink-dim transition-colors hover:text-accent"
    >
      <ArrowLeft size={14} strokeWidth={2} />
      All cases
    </Link>
  )
}

/** Empty hops is a correct, expected outcome — not a failure. */
function NoOutgoingFlow() {
  return (
    <div className="px-6 py-16 text-center">
      <h3 className="text-[15px] font-semibold text-ink">No outgoing transactions traced</h3>
      <p className="mx-auto mt-2.5 max-w-md text-[13px] leading-relaxed text-ink-dim">
        Tracing follows funds that this address has spent. Nothing was spent from it in
        the range examined, so there is no flow to draw. This is common for
        deposit-only and reserve addresses, which receive funds without sending them.
      </p>
      <p className="mx-auto mt-3 max-w-md text-[12px] leading-relaxed text-ink-faint">
        Incoming deposits are not followed, so an address can have real transaction
        history and still show no hops.
      </p>
    </div>
  )
}

function GraphLoading() {
  return (
    <div className="flex h-full items-center justify-center">
      <span className="text-[13px] text-ink-faint">Rendering fund flow…</span>
    </div>
  )
}

function NodeInspector({ node, matched, vasp }) {
  if (!node) {
    return (
      <aside className="border-line p-5 lg:border-l">
        <p className="text-[13px] leading-relaxed text-ink-faint">
          Select a node in the graph to see its full address and where it appears in
          the hop trail.
        </p>
      </aside>
    )
  }

  if (node.kind === NODE_KIND.UNKNOWN_PAYER) {
    return (
      <aside className="border-line p-5 lg:border-l">
        <h3 className="text-[13px] font-semibold text-ink">Payer not recorded</h3>
        <p className="mt-2.5 text-[13px] leading-relaxed text-ink-dim">
          One of the {node.candidateCount} addresses at hop {node.hopIndex} sent these funds
          onward. A hop record stores the depth it was reached at and the transaction
          that paid it, but not the address that did the paying.
        </p>
      </aside>
    )
  }

  const isSeed = node.kind === NODE_KIND.SEED

  return (
    <aside className="border-line p-5 lg:border-l">
      <h3 className="text-[13px] font-semibold text-ink">
        {isSeed ? 'Query address' : 'Traced address'}
      </h3>

      <div className="mt-3 rounded-sm border border-line bg-void p-3">
        <div className="flex items-start gap-2">
          <span className="data flex-1 text-[12px] leading-relaxed break-all text-ink">
            {node.address}
          </span>
          <CopyButton value={node.address} label="Copy address" />
        </div>
      </div>

      <dl className="mt-4 space-y-3">
        <div>
          <dt className="text-[12px] text-ink-faint">First appears at</dt>
          <dd className="mt-0.5 text-[13px] text-ink">
            {isSeed ? 'Seed of the trace' : `Hop ${node.hopIndex}`}
          </dd>
        </div>
        {isSeed && matched ? (
          <div>
            <dt className="text-[12px] text-ink-faint">Attribution</dt>
            <dd className="mt-0.5 inline-flex items-center gap-2 text-[13px] text-ink">
              <span className="h-1.5 w-1.5 rounded-full bg-match" aria-hidden="true" />
              {vasp}
            </dd>
          </div>
        ) : null}
      </dl>

      <a
        href={`https://mempool.space/address/${encodeURIComponent(node.address)}`}
        target="_blank"
        rel="noreferrer noopener"
        className="mt-5 inline-flex items-center gap-1.5 text-[12px] text-ink-dim transition-colors hover:text-accent"
      >
        View on mempool.space
        <ExternalLink size={12} strokeWidth={2} />
      </a>
    </aside>
  )
}

/**
 * Explains the one place the graph cannot be literal. Shown only when the trace
 * actually contains an ambiguous level.
 */
function PayerNotice() {
  return (
    <div className="mt-4 flex items-start gap-2.5 rounded-md border border-line bg-surface px-4 py-3">
      <Info size={15} strokeWidth={2} className="mt-0.5 shrink-0 text-ink-faint" />
      <p className="text-[12px] leading-relaxed text-ink-dim">
        A hop record stores the depth an address was reached at and the transaction
        that paid it, but not the address that sent the funds. Where more than one
        address sits at the previous hop, the graph routes those edges through a
        &ldquo;payer not recorded&rdquo; node instead of picking one, so no transfer is
        drawn that the trace did not observe.
      </p>
    </div>
  )
}

function HopLedger({ hops }) {
  const ordered = useMemo(
    () => [...hops].sort((a, b) => (a.hop_index ?? 0) - (b.hop_index ?? 0)),
    [hops]
  )

  return (
    <Panel title="Hop trail" className="mt-6" bodyClassName="">
      <div className="max-h-[520px] overflow-auto">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-surface">
            <tr className="border-b border-line">
              {['Hop', 'Destination address', 'Transaction', 'Amount (BTC)', 'Timestamp'].map((h) => (
                <th key={h} scope="col" className="px-5 py-2.5 text-[12px] font-medium text-ink-faint">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ordered.map((hop, i) => (
              <tr
                key={`${hop.tx_hash}-${hop.address}-${i}`}
                className="border-b border-line/60 transition-colors last:border-b-0 hover:bg-raised"
              >
                <td className="px-5 py-2.5">
                  <span className="data text-[13px] tabular-nums text-ink-faint">
                    {hop.hop_index}
                  </span>
                </td>
                <td className="max-w-[240px] px-5 py-2.5">
                  <MonoValue value={hop.address} head={12} tail={8} />
                </td>
                <td className="max-w-[220px] px-5 py-2.5">
                  <span className="inline-flex min-w-0 items-center gap-1.5">
                    <MonoValue value={hop.tx_hash} head={10} tail={6} tone="dim" />
                    <a
                      href={`${EXPLORER_TX}${encodeURIComponent(hop.tx_hash)}`}
                      target="_blank"
                      rel="noreferrer noopener"
                      title="Open transaction on mempool.space"
                      className="shrink-0 p-1 text-ink-faint transition-colors hover:text-accent"
                    >
                      <ExternalLink size={12} strokeWidth={2} />
                    </a>
                  </span>
                </td>
                <td className="px-5 py-2.5">
                  <span className="data text-[13px] tabular-nums text-ink">
                    {formatBtc(hop.amount_btc)}
                  </span>
                </td>
                <td className="px-5 py-2.5">
                  <span className="data text-[12px] whitespace-nowrap text-ink-dim">
                    {formatTimestamp(hop.timestamp)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

function DetailSkeleton() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-6 h-6 w-72" />
      <Skeleton className="mt-3 h-3.5 w-96" />
      <div className="mt-7 rounded-md border border-line bg-surface p-5">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i}>
              <Skeleton className="h-2.5 w-20" />
              <Skeleton className="mt-2.5 h-3.5 w-28" />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-6 h-[440px] rounded-md border border-line bg-surface">
        <div className="flex h-full items-center justify-center">
          <span className="text-[13px] text-ink-faint">Loading trace…</span>
        </div>
      </div>
    </div>
  )
}
