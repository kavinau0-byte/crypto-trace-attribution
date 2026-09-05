import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
// `three` is already in the tree as react-force-graph-3d's own dependency, held
// at a single version by the `three` override in package.json (a second copy is
// what caused the duplicate-three bug fixed in 03e7cfd). Building a custom node
// object requires it; this adds no new package.
import * as THREE from 'three'
import {
  LINK_KIND,
  NODE_KIND,
  nodeColor,
  nodeSize,
  particleColor,
  particleCount,
} from '../lib/graph'
import { formatBtc, truncateMiddle } from '../lib/format'

const BACKGROUND = '#0b0e14'

/** Passed to ForceGraph3D and reused to size the halo from the same radius. */
const NODE_REL_SIZE = 4

/**
 * Particle speed is progress-along-the-edge per frame, so 0.006 is a ~2.8s
 * traverse at 60fps: slow enough to read as direction, far from strobing.
 */
const PARTICLE_SPEED = 0.006
/** Roughly an eighth of a hop node's radius — an accent on the line, not a bead. */
const PARTICLE_WIDTH = 1.1

/**
 * Halo. A sprite with a radial-gradient texture, so the edge falls off to
 * nothing instead of ending on the hard rim a scaled-up sphere would give.
 * One texture is built lazily and shared by every halo that ever renders.
 */
const HALO_SCALE = 4.2 // multiples of the node's rendered radius
const HALO_OPACITY = 0.38

let haloTexture = null
function getHaloTexture() {
  if (haloTexture) return haloTexture
  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  const mid = size / 2
  const gradient = ctx.createRadialGradient(mid, mid, 0, mid, mid, mid)
  // White here; the sprite material tints it. Alpha does the shaping.
  gradient.addColorStop(0, 'rgba(255,255,255,0.55)')
  gradient.addColorStop(0.35, 'rgba(255,255,255,0.16)')
  gradient.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  haloTexture = new THREE.CanvasTexture(canvas)
  return haloTexture
}

/**
 * Which nodes get a halo. matched_vasp is attributed to the seed and never to
 * a hop node (tracing_engine/engine.py), so today this is exactly the seed —
 * keyed on the property as well as the kind so it still holds if that changes.
 */
function hasHalo(node) {
  return node?.kind === NODE_KIND.SEED || Boolean(node?.matchedVasp)
}

/**
 * A halo sized from the node it sits behind. Additive blending over the
 * near-black ground reads as light rather than as a grey disc, and
 * `depthWrite: false` keeps it from punching a hole in what is behind it.
 */
function makeHalo(node, color) {
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: getHaloTexture(),
      color: new THREE.Color(color),
      transparent: true,
      opacity: HALO_OPACITY,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
  )
  // Matches how the library derives a node's radius: nodeRelSize * cbrt(nodeVal).
  const radius = NODE_REL_SIZE * Math.cbrt(nodeSize(node) || 1)
  const extent = radius * HALO_SCALE
  sprite.scale.set(extent, extent, 1)
  sprite.renderOrder = -1 // behind the node sphere
  // The glow is decoration, not a target. A sprite raycasts against its whole
  // quad including the transparent falloff, which here is several times the
  // node's width — leaving it hittable would let the halo swallow clicks aimed
  // at the background or at a neighbouring node.
  sprite.raycast = () => {}
  return sprite
}

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

  // One budget decision for the whole graph, not per edge: `particleCount`
  // needs the total edge count, and recomputing it per accessor call would be
  // a per-frame cost for a value that only changes when the trace does.
  const linkCount = data.links.length
  const particlesPerLink = useCallback(
    (link) => particleCount(link, linkCount),
    [linkCount]
  )

  /**
   * The halo. `nodeThreeObjectExtend` keeps the library's own sphere and adds
   * this as a child, so node colour, sizing and hit-testing are untouched.
   *
   * Returning null for everything else means those nodes take the default path
   * and cost nothing extra. Both accessors are memoised because the library
   * rebuilds every node object whenever their identity changes.
   */
  const nodeHalo = useCallback(
    (node) => (hasHalo(node) ? makeHalo(node, nodeColor(node, { matched })) : null),
    [matched]
  )
  // Predicate only — deliberately does NOT call nodeHalo, which would build and
  // discard a sprite (and its material) for every node on every rebuild.
  const extendNodeObject = useCallback(hasHalo, [])

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

  /*
   * Framing the view. zoomToFit works well once there is a real spread of nodes,
   * but on a two- or three-node trace the bounding box is so small that it puts
   * the camera inside the sphere. Below that threshold the camera is placed at a
   * fixed, readable distance from the origin instead, which is where the force
   * layout centres the graph.
   */
  const frame = useCallback(
    (duration) => {
      const fg = fgRef.current
      if (!fg) return
      const n = graph.nodes.length
      if (n <= 12) {
        fg.cameraPosition({ x: 0, y: 0, z: n <= 3 ? 170 : 300 }, { x: 0, y: 0, z: 0 }, duration)
      } else {
        fg.zoomToFit(duration, n <= 60 ? 90 : 60)
      }
    },
    [graph.nodes.length]
  )

  // Frame the graph early so a large trace isn't a blank canvas while the
  // simulation settles, then frame it properly once it does.
  const ticks = useRef(0)
  useEffect(() => {
    ticks.current = 0
  }, [data])

  const handleEngineTick = useCallback(() => {
    ticks.current += 1
    if (ticks.current === 20) frame(0)
  }, [frame])

  const handleEngineStop = useCallback(() => frame(600), [frame])

  useEffect(() => {
    // Loosen the default charge a little so dense hop levels don't overlap.
    const charge = fgRef.current?.d3Force('charge')
    if (charge) charge.strength(-90)
  }, [data])

  const resetView = useCallback(() => frame(500), [frame])

  // A wide fan-out buries the query address in the middle of the cluster, so
  // there is a direct way back to it.
  const focusSeed = useCallback(() => {
    const seed = graph.nodes.find((n) => n.kind === NODE_KIND.SEED)
    if (!seed || !fgRef.current) return
    const { x = 0, y = 0, z = 0 } = seed
    const distance = 140
    const radius = Math.hypot(x, y, z)
    const camera = radius > 1
      ? { x: (x / radius) * (radius + distance), y: (y / radius) * (radius + distance), z: (z / radius) * (radius + distance) }
      : { x: 0, y: 0, z: distance }
    fgRef.current.cameraPosition(camera, seed, 900)
    onSelect?.(seed)
  }, [graph.nodes, onSelect])

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
          nodeRelSize={NODE_REL_SIZE}
          nodeVal={nodeSize}
          nodeColor={paint}
          nodeThreeObject={nodeHalo}
          nodeThreeObjectExtend={extendNodeObject}
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
          linkDirectionalParticles={particlesPerLink}
          linkDirectionalParticleWidth={PARTICLE_WIDTH}
          linkDirectionalParticleSpeed={PARTICLE_SPEED}
          linkDirectionalParticleColor={particleColor}
          cooldownTicks={140}
          onEngineTick={handleEngineTick}
          onEngineStop={handleEngineStop}
          enableNodeDrag={false}
        />
      ) : null}

      <div className="absolute top-3 right-3 flex gap-1.5">
        <button
          type="button"
          onClick={focusSeed}
          className="rounded-sm border border-white/10 bg-surface/55 px-2.5 py-1.5 text-[12px] font-medium text-ink-dim backdrop-blur-md transition-[background-color,backdrop-filter,border-color,color] hover:border-accent hover:bg-surface/75 hover:text-accent hover:backdrop-blur-lg active:bg-surface/90"
        >
          Find query address
        </button>
        <button
          type="button"
          onClick={resetView}
          className="rounded-sm border border-white/10 bg-surface/55 px-2.5 py-1.5 text-[12px] font-medium text-ink-dim backdrop-blur-md transition-[background-color,backdrop-filter,border-color,color] hover:border-accent hover:bg-surface/75 hover:text-accent hover:backdrop-blur-lg active:bg-surface/90"
        >
          Reset view
        </button>
      </div>

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
