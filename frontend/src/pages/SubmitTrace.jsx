import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Info, Search, X } from 'lucide-react'
import { describeApiError, isAbortError, submitTrace } from '../api/client'

// Matches the backend's TraceRequest default (schemas.py). Do not diverge.
const DEFAULT_MAX_HOPS = 4
const MIN_MAX_HOPS = 1
const MAX_MAX_HOPS = 8

/**
 * Depth where a trace reliably finishes in a demo-friendly time. Measured, not
 * guessed: depth 4 on a busy address has been observed running 30+ minutes,
 * because every extra hop multiplies the addresses fetched from mempool.space
 * and each fetch carries its own retry/backoff (tracing_engine/fetcher.py).
 */
const RECOMMENDED_MAX_HOPS = 2

export default function SubmitTrace() {
  const navigate = useNavigate()
  const [address, setAddress] = useState('')
  const [maxHops, setMaxHops] = useState(DEFAULT_MAX_HOPS)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [cancelled, setCancelled] = useState(false)

  // Held in a ref, not state: aborting must not depend on a re-render having
  // happened, and replacing it must never restart the request.
  const abortRef = useRef(null)

  // A trace left in flight when this screen goes away has nothing left to
  // resolve into, so drop the connection rather than leak it.
  useEffect(() => () => abortRef.current?.abort(), [])

  const cancelTrace = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setPending(false)
    setCancelled(true)
  }, [])

  async function onSubmit(event) {
    event.preventDefault()
    const trimmed = address.trim()
    // Sanity check only — the engine owns real address validation.
    if (!trimmed) {
      setError('Enter a Bitcoin address to trace.')
      return
    }
    setError(null)
    setCancelled(false)
    setPending(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const detail = await submitTrace({
        address: trimmed,
        maxHops,
        signal: controller.signal,
      })
      navigate(`/cases/${detail.id}`, { state: { case: detail } })
    } catch (err) {
      // Cancelling is a deliberate act, not a failure: cancelTrace has already
      // put the screen back, so there is nothing to report here.
      if (isAbortError(err)) return
      setError(describeApiError(err))
      setPending(false)
    } finally {
      if (abortRef.current === controller) abortRef.current = null
    }
  }

  if (pending) {
    return (
      <TraceRunning address={address.trim()} maxHops={maxHops} onCancel={cancelTrace} />
    )
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-14 sm:py-20">
      <h1 className="text-[26px] leading-tight font-semibold tracking-tight text-ink">
        Trace a Bitcoin address
      </h1>
      <p className="mt-3 max-w-xl text-[14px] leading-relaxed text-ink-dim">
        Follows outgoing spends from the address across the Bitcoin transaction graph
        and checks it against a curated list of known exchange addresses. Results are
        investigative leads, not identity confirmations.
      </p>

      <form onSubmit={onSubmit} className="mt-9">
        <label htmlFor="address" className="mb-2 block text-[13px] font-medium text-ink-dim">
          Bitcoin address
        </label>
        <div className="flex items-center gap-2 rounded-md border border-line-strong bg-surface px-4 transition-colors focus-within:border-accent">
          <Search size={16} strokeWidth={2} className="shrink-0 text-ink-faint" />
          <input
            id="address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            autoFocus
            placeholder="34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"
            className="data w-full bg-transparent py-3.5 text-[15px] text-ink placeholder:text-ink-faint/60 focus:outline-none"
          />
        </div>

        <div className="mt-7">
          <div className="flex items-baseline justify-between">
            <label htmlFor="max-hops" className="text-[13px] font-medium text-ink-dim">
              Hop depth
            </label>
            <span className="data text-[13px] tabular-nums text-accent">{maxHops}</span>
          </div>
          <input
            id="max-hops"
            type="range"
            min={MIN_MAX_HOPS}
            max={MAX_MAX_HOPS}
            step={1}
            value={maxHops}
            onChange={(e) => setMaxHops(Number(e.target.value))}
            className="mt-3 w-full accent-[#22d3eb]"
          />
          <p className="mt-2.5 text-[12px] leading-relaxed text-ink-faint">
            How many transaction hops to follow outward from the address. Each extra
            hop multiplies the addresses that have to be fetched from mempool.space,
            so busy addresses at higher depths can take several minutes.
          </p>
          {maxHops > RECOMMENDED_MAX_HOPS ? (
            <p className="mt-2 flex items-start gap-2 text-[12px] leading-relaxed text-ink-faint">
              <Info size={13} strokeWidth={2} className="mt-0.5 shrink-0" />
              <span>
                Depth {RECOMMENDED_MAX_HOPS} is the most predictable for timing. A busy
                address at depth 4 has been measured running 30+ minutes. Higher depths
                still work — you can cancel a run that is taking too long.
              </span>
            </p>
          ) : null}
        </div>

        {cancelled ? (
          <div className="mt-7 flex items-start gap-2.5 rounded-md border border-line bg-surface px-4 py-3">
            <Info size={15} strokeWidth={2} className="mt-0.5 shrink-0 text-ink-faint" />
            <div>
              <p className="text-[13px] leading-relaxed text-ink">
                Trace cancelled. This page stopped waiting for it.
              </p>
              <p className="mt-1 text-[12px] leading-relaxed text-ink-faint">
                The backend finishes a trace it has already started, so if this one
                completes it will still show up under Cases. Lowering the hop depth is
                the reliable way to get a faster result.
              </p>
            </div>
          </div>
        ) : null}

        {error ? (
          <div
            role="alert"
            className="mt-7 flex items-start gap-2.5 rounded-md border border-alert/35 bg-alert/10 px-4 py-3"
          >
            <AlertTriangle size={15} strokeWidth={2} className="mt-0.5 shrink-0 text-alert" />
            <p className="text-[13px] leading-relaxed text-ink">{error}</p>
          </div>
        ) : null}

        <button
          type="submit"
          className="mt-8 inline-flex items-center gap-2 rounded-sm border border-white/10 bg-accent/75 px-5 py-2.5 text-[13px] font-semibold text-void backdrop-blur transition-[background-color,backdrop-filter] hover:bg-accent/90 hover:backdrop-blur-md active:bg-accent"
        >
          Run trace
        </button>
      </form>
    </div>
  )
}

/**
 * A trace hits mempool.space once per address it walks, so it can run for
 * minutes. The wait shows elapsed time and what the engine is doing, so a slow
 * trace never reads as a frozen page.
 */
function TraceRunning({ address, maxHops, onCancel }) {
  const [elapsed, setElapsed] = useState(0)
  const startedAt = useRef(Date.now())

  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt.current) / 1000))
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const minutes = Math.floor(elapsed / 60)
  const seconds = String(elapsed % 60).padStart(2, '0')

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-14 sm:py-20" aria-live="polite" aria-busy="true">
      <h1 className="text-[26px] leading-tight font-semibold tracking-tight text-ink">
        Trace running
      </h1>
      <p className="mt-3 text-[14px] text-ink-dim">
        Walking outgoing spends to a depth of {maxHops} hop{maxHops === 1 ? '' : 's'}.
      </p>

      <div className="data mt-8 truncate text-[14px] text-accent" title={address}>
        {address}
      </div>

      <div className="scanline relative mt-5 h-0.5 overflow-hidden rounded-full bg-line" />

      <div className="mt-8 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-baseline gap-3">
          <span className="data text-[32px] tabular-nums text-ink">
            {minutes}:{seconds}
          </span>
          <span className="text-[13px] text-ink-faint">elapsed</span>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex shrink-0 items-center gap-2 rounded-sm border border-white/10 bg-surface/50 px-3.5 py-2 text-[13px] font-medium text-ink backdrop-blur-md transition-[background-color,backdrop-filter,border-color,color] hover:border-alert hover:bg-surface/70 hover:text-alert hover:backdrop-blur-lg active:bg-surface/90"
        >
          <X size={14} strokeWidth={2} />
          Cancel trace
        </button>
      </div>

      <div className="mt-8 space-y-2.5 border-t border-line pt-6">
        {[
          'Fetching transaction history from mempool.space',
          'Following outgoing spends hop by hop',
          'Grouping co-spent addresses into a cluster',
          'Checking the address and its cluster against known exchange tags',
        ].map((step) => (
          <div key={step} className="flex items-start gap-2.5">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-line-strong" aria-hidden="true" />
            <span className="text-[13px] leading-relaxed text-ink-dim">{step}</span>
          </div>
        ))}
      </div>

      <p className="mt-6 text-[12px] leading-relaxed text-ink-faint">
        Keep this tab open. The case is saved when the trace finishes. Cancelling
        stops this page waiting; the backend still finishes the run it started, so a
        cancelled trace may still appear under Cases.
      </p>
    </div>
  )
}
