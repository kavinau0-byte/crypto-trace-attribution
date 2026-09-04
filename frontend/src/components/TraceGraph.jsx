import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import { LINK_KIND, NODE_KIND, nodeColor, nodeSize } from '../lib/graph'
import { formatBtc, truncateMiddle } from '../lib/format'

const BACKGROUND = '#0b0e14'

/** Track the panel size so the canvas fills it and follows window resizes. */
function useElementSize() {
  const ref = useRef(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const observer = new ResizeObserver(([entry]) => {
      const box = entry.contentRect
      setSize({ width: Math.round(box.width), height: Math.round(box.height) })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return [ref, size]
}

export default function TraceGraph({ graph, matched, selectedId, onSelect }) {
  const [wrapRef, { width, height }] = useElementSize()
  const fgRef = useRef(null)

  // react-force-graph mutates the objects it is given (positions, and it swaps
  // link source/target ids for node references), so this must be a stable
  // identity for the life of the trace or the simulation restarts every render.
  const data = useMemo(
    () => ({ nodes: graph.nodes, links: graph.links }),
    [graph.nodes, graph.links]
  )

  const paint = useCallback((node) => nodeColor(node, { matched }), [matched])

  const nodeLabel = useCallback((node) => {
    if (node.kind === NODE_KIND.UNKNOWN_PAYER) {
      return tooltip(
        'Payer not recorded',
        `One of the ${node.candidateCount} addresses at hop ${node.hopIndex} sent these funds onward. The trace records hop depth, not the sending address.`
      )
    }
    const title = node.kind === NODE_KIND.SEED ? 'Query address' : `First reached at hop ${node.hopIndex}`
    return tooltip(title, node.address, true)
  }, [])

  const linkLabel = useCallback((link) => {
    if (link.kind === LINK_KIND.CANDIDATE) {
      return tooltip('Possible payer', 'This address sits one hop upstream. The trace does not record which upstream address paid.')
    }
    return tooltip(
      `${formatBtc(link.amountBtc)} BTC`,
      `tx ${truncateMiddle(link.txHash, 12, 10)}`,
      true
    )
  }, [])

  const linkColor = useCallback(
    (link) => (link.kind === LINK_KIND.CANDIDATE ? 'rgba(61,71,96,0.5)' : 'rgba(120,134,161,0.55)'),
    []
  )

  // Frame the whole graph once the layout settles.
  const handleEngineStop = useCallback(() => {
    fgRef.current?.zoomToFit(600, 60)
  }, [])

  useEffect(() => {
    // Loosen the default charge a little so dense hop levels don't overlap.
    const charge = fgRef.current?.d3Force('charge')
    if (charge) charge.strength(-90)
  }, [data])

  const resetView = useCallback(() => fgRef.current?.zoomToFit(500, 60), [])

  return (
    <div ref={wrapRef} className="relative h-full w-full">
      {width > 0 && height > 0 ? (
        <ForceGraph3D
          ref={fgRef}
          graphData={data}
          width={width}
          height={height}
          backgroundColor={BACKGROUND}
          showNavInfo={false}
          nodeRelSize={1}
          nodeVal={nodeSize}
          nodeColor={paint}
          nodeOpacity={0.95}
          nodeResolution={12}
          nodeLabel={nodeLabel}
          onNodeClick={(node) => onSelect?.(node)}
          onBackgroundClick={() => onSelect?.(null)}
          linkLabel={linkLabel}
          linkColor={linkColor}
          linkWidth={(l) => (l.kind === LINK_KIND.CANDIDATE ? 0.3 : 0.8)}
          linkOpacity={0.55}
          linkDirectionalArrowLength={(l) => (l.kind === LINK_KIND.CANDIDATE ? 0 : 3)}
          linkDirectionalArrowRelPos={1}
          linkDirectionalParticles={(l) => (l.kind === LINK_KIND.HOP ? 2 : 0)}
          linkDirectionalParticleWidth={1.1}
          linkDirectionalParticleSpeed={0.006}
          linkDirectionalParticleColor={() => '#22d3eb'}
          cooldownTicks={140}
          onEngineStop={handleEngineStop}
          enableNodeDrag={false}
        />
      ) : null}

      <button
        type="button"
        onClick={resetView}
        className="absolute top-3 right-3 rounded-sm border border-line-strong bg-surface/85 px-2.5 py-1.5 text-[12px] font-medium text-ink-dim backdrop-blur-sm transition-colors hover:border-accent hover:text-accent"
      >
        Reset view
      </button>

      <Legend matched={matched} hasUnknownPayer={graph.hasUnknownPayer} />

      {selectedId ? null : (
        <p className="pointer-events-none absolute bottom-3 left-4 text-[11px] text-ink-faint">
          Drag to rotate · scroll to zoom · click a node for details
        </p>
      )}
    </div>
  )
}

function Legend({ matched, hasUnknownPayer }) {
  const items = [
    { color: matched ? '#34d399' : '#22d3eb', label: matched ? 'Query address (VASP matched)' : 'Query address' },
    { color: '#75839d', label: 'Address reached by a hop' },
    ...(hasUnknownPayer ? [{ color: '#3d4760', label: 'Payer not recorded', ring: true }] : []),
  ]
  return (
    <ul className="pointer-events-none absolute top-3 left-4 space-y-1.5">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-2">
          <span
            className="h-2 w-2 shrink-0 rounded-full"
            style={
              item.ring
                ? { border: `1px dashed ${item.color}`, background: 'transparent' }
                : { background: item.color }
            }
            aria-hidden="true"
          />
          <span className="text-[11px] text-ink-faint">{item.label}</span>
        </li>
      ))}
    </ul>
  )
}

/**
 * Hover tooltips are rendered by the graph library outside the React tree, so
 * they are styled inline rather than with utility classes.
 */
function tooltip(title, body, mono = false) {
  const monoFamily = "'JetBrains Mono', ui-monospace, monospace"
  return `
    <div style="
      background:#131722;border:1px solid #2a3244;border-radius:4px;
      padding:7px 10px;max-width:340px;font-family:Inter,sans-serif;
      box-shadow:0 6px 20px rgba(0,0,0,.45);
    ">
      <div style="font-size:12px;font-weight:600;color:#e6eaf2;margin-bottom:3px;">${escapeHtml(title)}</div>
      <div style="
        font-size:11px;line-height:1.55;color:#96a0b5;word-break:break-all;
        ${mono ? `font-family:${monoFamily};` : ''}
      ">${escapeHtml(body)}</div>
    </div>`
}

function escapeHtml(value) {
  return String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  )
}
