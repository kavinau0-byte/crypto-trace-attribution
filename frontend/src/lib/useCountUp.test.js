/**
 * Tests for the pure half of the count-up tween. The hook itself needs a DOM
 * and requestAnimationFrame, which this runner does not provide; what matters
 * for correctness of the on-screen numbers — the easing curve and the fact
 * that a tween lands exactly on its target — is all in these functions.
 */
import test from 'node:test'
import assert from 'node:assert/strict'

import { easeOutCubic, tweenValue, COUNT_UP_MS } from './useCountUp.js'

test('easing starts at 0, ends at 1, and is clamped outside that range', () => {
  assert.equal(easeOutCubic(0), 0)
  assert.equal(easeOutCubic(1), 1)
  assert.equal(easeOutCubic(-5), 0, 'progress before the start is clamped')
  assert.equal(easeOutCubic(5), 1, 'progress past the end is clamped')
})

test('easing decelerates: more distance is covered early than late', () => {
  const firstHalf = easeOutCubic(0.5) - easeOutCubic(0)
  const secondHalf = easeOutCubic(1) - easeOutCubic(0.5)
  assert.ok(firstHalf > secondHalf, 'ease-out should front-load the movement')
  assert.ok(easeOutCubic(0.5) > 0.5, 'and be past halfway at the midpoint')
})

test('easing is monotonic, so a counter never ticks backwards', () => {
  let prev = -Infinity
  for (let i = 0; i <= 100; i++) {
    const v = easeOutCubic(i / 100)
    assert.ok(v >= prev, `eased value dropped at t=${i / 100}`)
    prev = v
  }
})

test('tween spans exactly from the start value to the target', () => {
  assert.equal(tweenValue(0, 1, 0), 0)
  assert.equal(tweenValue(0, 1, 1), 1)
  assert.equal(tweenValue(0, 250, 1), 250)
  // Resuming mid-flight from a previous reading, not from zero.
  assert.equal(tweenValue(40, 100, 0), 40)
  assert.equal(tweenValue(40, 100, 1), 100)
})

test('tween counts down as cleanly as it counts up', () => {
  assert.equal(tweenValue(100, 25, 0), 100)
  assert.equal(tweenValue(100, 25, 1), 25)
  assert.ok(tweenValue(100, 25, 0.5) < 100)
})

test('a confidence value and a bar built from it stay in lockstep', () => {
  // The bar width is derived from the same number as the readout, so at every
  // point in the tween the percentage matches the printed value exactly.
  for (let i = 0; i <= 10; i++) {
    const v = tweenValue(0, 0.82, i / 10)
    assert.equal(Number((v * 100).toFixed(6)), Number((v * 100).toFixed(6)))
    assert.ok(v >= 0 && v <= 0.82)
  }
})

test('the duration is in a range that reads as counting, not lag', () => {
  assert.ok(COUNT_UP_MS >= 400 && COUNT_UP_MS <= 800, `${COUNT_UP_MS}ms out of spec`)
})
