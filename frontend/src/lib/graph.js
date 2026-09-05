/**
 * Turns a TraceResult into nodes and links for the 3D fund-flow graph.
 *
 * ---------------------------------------------------------------------------
 * Why this file is more careful than "one edge per hop" sounds
 * ---------------------------------------------------------------------------
 * A hop record is
 * `{ hop_index, address, tx_hash, timestamp, amount_btc, from_address }`.
 * `from_address` is the address that actually sent the funds — the engine
 * records the BFS node whose outgoing transaction it was following
 * (tracing_engine/hop_tracer.py), so the payer is known exactly rather than
 * inferred. When it is present, this file draws the real
 * `from_address -> address` edge, which is the normal path.
 *
 * The fallback below exists because `from_address` is Optional in the
 * contract. Hop records written before the field was added — cases already
 * persisted in the database — have it as null, and those still have to render.
 * Historically that was the ONLY path, and it was genuinely lossy: a hop
 * recorded the depth at which an address was reached but not who paid it, so
 * for hop_index N >= 1 the payer was merely "one of the addresses at level
 * N-1". On real traces that was not a corner case — a live trace of a
 * 4-transaction address at max_hops=2 produced 4 addresses at level 0 and 93
 * at level 1, so 93 edges had 4 candidate sources each, and all 93 were routed
 * through a single placeholder node.
 *
 * So, for a hop with no `from_address`:
 *   - Guessing a parent would draw fund movements that did not happen.
 *   - Drawing an edge from every candidate would multiply the edge count and
 *     still misrepresent the flow.
 *   - So: when the previous level has exactly one address, the payer IS
 *     determined and the edge is drawn directly. When it has several, those
 *     edges pass through one explicit `unknown-payer` node per level, labelled
 *     in the UI as "payer not recorded". Every candidate at the previous level
 *     links into it, which is exactly the claim the data supports: one of these
 *     addresses paid onward, and the record does not say which.
 *
 * The placeholder is created lazily, only for hops that actually need it, so a
 * trace from the current engine never shows one. A mixed trace (some hops with
 * a payer, some without) renders each hop by what its own record supports.
 *
 * Each hop record still contributes exactly one directed, labelled edge into
 * its destination address, so the hop ledger and the graph stay in step.
 */

export const NODE_KIND = {
  SEED: 'seed',
  ADDRESS: 'address',
  UNKNOWN_PAYER: 'unknown-payer',
}

export const LINK_KIND = {
  /** Straight from a hop record: this transaction paid this address. */
  HOP: 'hop',
  /**
   * Fallback only: this address sits at the previous level of a hop whose
   * record has no `from_address`, so it is a possible — not confirmed — payer.
   */
  CANDIDATE: 'candidate',
}

/**
 * @param {object} trace - the `trace` object from a CaseDetail response.
 * @returns {{nodes: object[], links: object[], maxHopIndex: number,
 *            hasUnknownPayer: boolean, addressCount: number}}
 */
export function buildTraceGraph(trace) {
  const seedId = trace?.query_address || ''
  const hops = Array.isArray(trace?.hops) ? trace.hops : []

  const nodes = new Map()
  const links = []

  if (!seedId) {
    return { nodes: [], links: [], maxHopIndex: 0, hasUnknownPayer: false, addressCount: 0 }
  }

  // The VASP attribution is evaluated against the seed address and its
  // co-spend cluster only — `match_vasp()` never walks forward into the hops
  // (tracing_engine/engine.py). So a non-null matched_vasp always belongs to
  // the seed node, and no hop node may be highlighted as the match.
  const matchedVasp = trace?.matched_vasp || null

  nodes.set(seedId, {
    id: seedId,
    kind: NODE_KIND.SEED,
    address: seedId,
    hopIndex: null,
    matchedVasp,
    label: 'Query address',
  })

  // Group hop records by depth, preserving the order the engine emitted them.
  const byLevel = new Map()
  for (const hop of hops) {
    const level = Number(hop?.hop_index)
    if (!Number.isFinite(level)) continue
    if (!byLevel.has(level)) byLevel.set(level, [])
    byLevel.get(level).push(hop)
  }

  const levels = [...byLevel.keys()].sort((a, b) => a - b)
  const addressesAtLevel = new Map()
  for (const level of levels) {
    addressesAtLevel.set(level, [...new Set(byLevel.get(level).map((h) => h.address).filter(Boolean))])
  }

  let hasUnknownPayer = false

  // The placeholder for a level is built at most once, and only if a hop at
  // that level actually lacks a payer. Levels whose hops all carry
  // `from_address` never create one.
  const ensureFallbackSource = (level) => {
    const source = resolveSource({ level, seedId, addressesAtLevel })
    if (source.kind !== NODE_KIND.UNKNOWN_PAYER) return source

    hasUnknownPayer = true
    if (!nodes.has(source.id)) {
      nodes.set(source.id, {
        id: source.id,
        kind: NODE_KIND.UNKNOWN_PAYER,
        hopIndex: level - 1,
        candidateCount: source.candidates.length,
        label: `Payer at hop ${level - 1} not recorded`,
      })
      // Every address at the previous level is a possible payer.
      for (const candidate of source.candidates) {
        links.push({
          source: candidate,
          target: source.id,
          kind: LINK_KIND.CANDIDATE,
          hopIndex: level - 1,
        })
      }
    }
    return source
  }

  for (const level of levels) {
    for (const hop of byLevel.get(level)) {
      const address = hop?.address
      if (!address) continue

      if (!nodes.has(address)) {
        nodes.set(address, {
          id: address,
          kind: NODE_KIND.ADDRESS,
          address,
          hopIndex: level, // depth at which this address was first reached
          label: `Hop ${level}`,
        })
      }

      // The normal path: the record names the payer, so draw the real edge.
      const payer = typeof hop.from_address === 'string' && hop.from_address ? hop.from_address : null

      let sourceId
      let payerKnown
      if (payer) {
        sourceId = payer
        payerKnown = true
        // The payer is normally already a node (the seed, or an address from
        // the previous level). Create it defensively if a record ever names a
        // payer that no hop at the previous level introduced.
        if (!nodes.has(sourceId)) {
          nodes.set(sourceId, {
            id: sourceId,
            kind: NODE_KIND.ADDRESS,
            address: sourceId,
            hopIndex: Math.max(level - 1, 0),
            label: `Hop ${Math.max(level - 1, 0)}`,
          })
        }
      } else {
        // Fallback for records predating `from_address`.
        const source = ensureFallbackSource(level)
        sourceId = source.id
        payerKnown = source.kind !== NODE_KIND.UNKNOWN_PAYER
      }

      // Defensive: never emit a self-loop if a record ever names an address as
      // its own predecessor.
      if (sourceId === address) continue

      links.push({
        source: sourceId,
        target: address,
        kind: LINK_KIND.HOP,
        hopIndex: level,
        txHash: hop.tx_hash,
        amountBtc: hop.amount_btc,
        timestamp: hop.timestamp,
        payerKnown,
      })
    }
  }

  return {
    nodes: [...nodes.values()],
    links,
    maxHopIndex: levels.length ? Math.max(...levels) : 0,
    hasUnknownPayer,
    addressCount: [...nodes.values()].filter((n) => n.kind !== NODE_KIND.UNKNOWN_PAYER).length,
  }
}

/**
 * Fallback payer resolution for a hop record with no `from_address`.
 * Only reached for data predating that field.
 */
function resolveSource({ level, seedId, addressesAtLevel }) {
  // Depth 0 is always spent by the seed — the BFS frontier starts there.
  if (level === 0) return { id: seedId, kind: NODE_KIND.SEED, candidates: [seedId] }

  const previous = addressesAtLevel.get(level - 1) || []

  // A level with no recorded predecessor shouldn't occur (BFS levels are
  // contiguous), but if it did, anchoring to the seed is the only claim the
  // data supports: these funds came from somewhere along the seed's chain.
  if (previous.length === 0) return { id: seedId, kind: NODE_KIND.SEED, candidates: [seedId] }

  // Exactly one candidate means the payer IS determined.
  if (previous.length === 1) {
    return { id: previous[0], kind: NODE_KIND.ADDRESS, candidates: previous }
  }

  return { id: `unknown-payer:${level}`, kind: NODE_KIND.UNKNOWN_PAYER, candidates: previous }
}

/** Node colours: seed reads as the subject, depth fades into the background. */
export function nodeColor(node, { matched }) {
  if (node.kind === NODE_KIND.SEED) return matched ? '#34d399' : '#22d3eb'
  if (node.kind === NODE_KIND.UNKNOWN_PAYER) return '#3d4760'
  // Subtle depth gradient — further from the seed, closer to the background.
  const shades = ['#8f9cb5', '#75839d', '#5e6b84', '#4d596e', '#404b5e']
  return shades[Math.min(node.hopIndex ?? 0, shades.length - 1)]
}

/**
 * Sphere volume, not radius — react-force-graph derives the radius as
 * `nodeRelSize * cbrt(nodeVal)`, so these are cubed to get the visual ratio.
 * The seed reads roughly 2.5x the radius of a hop node.
 */
export function nodeSize(node) {
  if (node.kind === NODE_KIND.SEED) return 18
  if (node.kind === NODE_KIND.UNKNOWN_PAYER) return 0.7
  return 1.1
}
