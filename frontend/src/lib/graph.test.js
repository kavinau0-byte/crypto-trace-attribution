/**
 * Tests for buildTraceGraph — run with `npm test` (node's built-in test
 * runner, no extra dependency).
 *
 * The behaviour under test: a hop record carrying `from_address` must draw the
 * real payer -> destination edge, while records without one (data predating
 * that field) must still fall back to the "payer not recorded" placeholder.
 */
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildTraceGraph,
  NODE_KIND,
  LINK_KIND,
  particleCount,
  particleColor,
  PARTICLE_COLOR_KNOWN,
  PARTICLE_COLOR_UNKNOWN,
  PARTICLE_MAX_EDGES,
  PARTICLE_RICH_MAX_EDGES,
} from './graph.js'

const SEED = 'seed_addr'

function hop(hop_index, address, from_address, extra = {}) {
  return {
    hop_index,
    address,
    from_address,
    tx_hash: `tx_${hop_index}_${address}`,
    timestamp: '2026-09-01T10:00:00Z',
    amount_btc: 0.1,
    ...extra,
  }
}

const hopLinks = (g) => g.links.filter((l) => l.kind === LINK_KIND.HOP)
const edge = (g, target) => hopLinks(g).find((l) => l.target === target)

test('from_address draws the real edge at hop_index 0', () => {
  const g = buildTraceGraph({ query_address: SEED, hops: [hop(0, 'B', SEED)] })
  assert.equal(edge(g, 'B').source, SEED)
  assert.equal(edge(g, 'B').payerKnown, true)
  assert.equal(g.hasUnknownPayer, false)
})

test('a multi-address level routes each hop to its own real payer', () => {
  // The exact shape that used to collapse into one placeholder: several
  // addresses at level 0, each paying different addresses at level 1.
  const hops = [
    hop(0, 'A1', SEED),
    hop(0, 'A2', SEED),
    hop(0, 'A3', SEED),
    hop(1, 'B1', 'A1'),
    hop(1, 'B2', 'A2'),
    hop(1, 'B3', 'A3'),
  ]
  const g = buildTraceGraph({ query_address: SEED, hops })

  assert.equal(g.hasUnknownPayer, false, 'no placeholder when every hop names its payer')
  assert.equal(
    g.nodes.filter((n) => n.kind === NODE_KIND.UNKNOWN_PAYER).length,
    0,
  )
  assert.equal(edge(g, 'B1').source, 'A1')
  assert.equal(edge(g, 'B2').source, 'A2')
  assert.equal(edge(g, 'B3').source, 'A3')
  // One edge per hop record — the ledger and the graph stay in step.
  assert.equal(hopLinks(g).length, hops.length)
})

test('fallback placeholder still appears when from_address is missing', () => {
  const hops = [
    hop(0, 'A1', null),
    hop(0, 'A2', null),
    hop(1, 'B1', null),
    hop(1, 'B2', null),
  ]
  const g = buildTraceGraph({ query_address: SEED, hops })

  assert.equal(g.hasUnknownPayer, true)
  const placeholders = g.nodes.filter((n) => n.kind === NODE_KIND.UNKNOWN_PAYER)
  assert.equal(placeholders.length, 1, 'one placeholder for level 1')
  assert.equal(edge(g, 'B1').source, placeholders[0].id)
  assert.equal(edge(g, 'B1').payerKnown, false)
  // Level 0 is unambiguous even without the field: the seed spent it.
  assert.equal(edge(g, 'A1').source, SEED)
})

test('a mixed trace renders each hop by what its own record supports', () => {
  const hops = [
    hop(0, 'A1', SEED),
    hop(0, 'A2', SEED),
    hop(1, 'B1', 'A1'), // knows its payer
    hop(1, 'B2', null), // predates the field
  ]
  const g = buildTraceGraph({ query_address: SEED, hops })

  assert.equal(edge(g, 'B1').source, 'A1')
  assert.equal(edge(g, 'B1').payerKnown, true)
  assert.equal(g.hasUnknownPayer, true)
  const placeholder = g.nodes.find((n) => n.kind === NODE_KIND.UNKNOWN_PAYER)
  assert.equal(edge(g, 'B2').source, placeholder.id)
  assert.equal(edge(g, 'B2').payerKnown, false)
})

test('a single-address previous level still resolves without a placeholder', () => {
  const g = buildTraceGraph({
    query_address: SEED,
    hops: [hop(0, 'A', null), hop(1, 'B', null)],
  })
  assert.equal(g.hasUnknownPayer, false)
  assert.equal(edge(g, 'B').source, 'A')
})

test('empty-string from_address is treated as missing, not as a node id', () => {
  const g = buildTraceGraph({
    query_address: SEED,
    hops: [hop(0, 'A1', ''), hop(0, 'A2', ''), hop(1, 'B', '')],
  })
  assert.ok(g.nodes.every((n) => n.id !== ''))
  assert.equal(g.hasUnknownPayer, true)
})

test('a self-referencing record never produces a self-loop', () => {
  const g = buildTraceGraph({ query_address: SEED, hops: [hop(1, 'X', 'X')] })
  assert.equal(hopLinks(g).filter((l) => l.source === l.target).length, 0)
})

test('hop metadata is carried onto the edge', () => {
  const g = buildTraceGraph({ query_address: SEED, hops: [hop(0, 'B', SEED)] })
  const l = edge(g, 'B')
  assert.equal(l.txHash, 'tx_0_B')
  assert.equal(l.amountBtc, 0.1)
  assert.equal(l.timestamp, '2026-09-01T10:00:00Z')
})

test('a null timestamp (unconfirmed hop) still renders', () => {
  const g = buildTraceGraph({
    query_address: SEED,
    hops: [hop(0, 'B', SEED, { timestamp: null })],
  })
  assert.equal(edge(g, 'B').timestamp, null)
})

test('an empty trace returns an empty graph', () => {
  const g = buildTraceGraph({ query_address: '', hops: [] })
  assert.deepEqual(g.nodes, [])
  assert.deepEqual(g.links, [])
})

/* --------------------------------------------------------------------------
 * Flow particles
 * ------------------------------------------------------------------------ */

test('particles travel payer -> recipient, matching the link direction', () => {
  // three-forcegraph moves a particle along `source + (target - source) * t`
  // with t advancing by a POSITIVE linkDirectionalParticleSpeed each frame, so
  // "source is the payer" is what makes the animation show real fund movement.
  const hops = [hop(0, 'A1', SEED), hop(1, 'B1', 'A1')]
  const g = buildTraceGraph({ query_address: SEED, hops })

  for (const h of hops) {
    const l = hopLinks(g).find((x) => x.target === h.address)
    assert.equal(l.source, h.from_address, 'edge must start at the recorded payer')
    assert.equal(l.target, h.address, 'edge must end at the address that was paid')
    assert.notEqual(l.source, l.target)
  }
})

test('candidate edges carry no particles', () => {
  // A candidate edge means "this address might have paid". Animating flow along
  // it would assert a transfer the trace never observed.
  const g = buildTraceGraph({
    query_address: SEED,
    hops: [hop(0, 'A1', null), hop(0, 'A2', null), hop(1, 'B', null)],
  })
  const candidates = g.links.filter((l) => l.kind === LINK_KIND.CANDIDATE)
  assert.ok(candidates.length > 0, 'fixture should produce candidate edges')
  for (const l of candidates) assert.equal(particleCount(l, g.links.length), 0)
})

test('particle colour separates known from unknown payers', () => {
  const g = buildTraceGraph({
    query_address: SEED,
    hops: [hop(0, 'A1', SEED), hop(0, 'A2', SEED), hop(1, 'B1', 'A1'), hop(1, 'B2', null)],
  })
  assert.equal(particleColor(edge(g, 'B1')), PARTICLE_COLOR_KNOWN)
  assert.equal(particleColor(edge(g, 'B2')), PARTICLE_COLOR_UNKNOWN)
  // Level 0 is unambiguous even without from_address: the seed spent it.
  assert.equal(particleColor(edge(g, 'A1')), PARTICLE_COLOR_KNOWN)
})

test('particle density steps down as the graph grows, then off', () => {
  const link = { kind: LINK_KIND.HOP, payerKnown: true }
  assert.equal(particleCount(link, 10), 3, 'small graph gets the richer flow')
  assert.equal(particleCount(link, PARTICLE_RICH_MAX_EDGES), 3)
  assert.equal(particleCount(link, PARTICLE_RICH_MAX_EDGES + 1), 2)
  assert.equal(particleCount(link, PARTICLE_MAX_EDGES), 2)
  assert.equal(particleCount(link, PARTICLE_MAX_EDGES + 1), 0, 'past budget: static edges')
  // The real 1776-hop case must land in the "off" band.
  assert.equal(particleCount(link, 1776), 0)
})

test('particle count never exceeds 3 per edge at any graph size', () => {
  const link = { kind: LINK_KIND.HOP, payerKnown: true }
  for (const n of [1, 50, 119, 120, 121, 399, 400, 401, 5000]) {
    const c = particleCount(link, n)
    assert.ok(c >= 0 && c <= 3, `${n} edges -> ${c} particles`)
  }
})
