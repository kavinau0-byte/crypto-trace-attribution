/**
 * Turns a TraceResult into nodes and links for the 3D fund-flow graph.
 *
 * ---------------------------------------------------------------------------
 * Why this file is more careful than "one edge per hop" sounds
 * ---------------------------------------------------------------------------
 * A hop record is `{ hop_index, address, tx_hash, timestamp, amount_btc }`.
 * It records the BFS *depth* at which an address was reached, and the
 * transaction that paid it — but NOT which address did the paying. For
 * hop_index 0 that is fine: the engine's BFS starts at the seed, so every
 * hop_index-0 record is unambiguously `seed -> address`.
 *
 * For hop_index N >= 1 the payer is one of the addresses at level N-1, and the
 * contract does not say which. On real traces this is not a corner case: a
 * live trace of a 4-transaction address at max_hops=2 produced 4 addresses at
 * level 0 and 93 addresses at level 1, so 93 edges have 4 candidate sources
 * each.
 *
 * Three options, and why this one:
 *   - Guessing a parent would draw fund movements that did not happen.
 *   - Drawing an edge from every candidate would multiply the edge count and
 *     still misrepresent the flow.
 *   - So: when the previous level has exactly one address, the payer IS known
 *     and the edge is drawn directly. When it has several, the edges pass
 *     through one explicit `unknown-payer` node per level, labelled in the UI
 *     as "payer not recorded". Every candidate at the previous level links
 *     into it, which is exactly the claim the data supports: one of these
 *     addresses paid onward, and the trace does not record which.
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
  /** This address sits at the previous level, so it is a possible payer. */
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

  for (const level of levels) {
    const source = resolveSource({ level, seedId, addressesAtLevel })

    if (source.kind === NODE_KIND.UNKNOWN_PAYER) {
      hasUnknownPayer = true
      if (!nodes.has(source.id)) {
        nodes.set(source.id, {
          id: source.id,
          kind: NODE_KIND.UNKNOWN_PAYER,
          hopIndex: level - 1,
          candidateCount: source.candidates.length,
          label: `Payer at hop ${level - 1} not recorded`,
        })
      }
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

      // Defensive: never emit a self-loop if the engine ever repeats an address
      // as its own sole predecessor.
      if (source.id === address) continue

      links.push({
        source: source.id,
        target: address,
        kind: LINK_KIND.HOP,
        hopIndex: level,
        txHash: hop.tx_hash,
        amountBtc: hop.amount_btc,
        timestamp: hop.timestamp,
        payerKnown: source.kind !== NODE_KIND.UNKNOWN_PAYER,
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

export function nodeSize(node) {
  if (node.kind === NODE_KIND.SEED) return 9
  if (node.kind === NODE_KIND.UNKNOWN_PAYER) return 2.5
  return 3.5
}
