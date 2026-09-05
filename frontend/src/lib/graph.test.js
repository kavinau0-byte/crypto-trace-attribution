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

import { buildTraceGraph, NODE_KIND, LINK_KIND } from './graph.js'

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
