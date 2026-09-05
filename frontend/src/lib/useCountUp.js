/**
 * Count-up tween for stat numbers.
 *
 * The point of this file is that a stat and any bar drawn from it animate off
 * ONE value. `useCountUp` returns a number; the caller renders every
 * representation of that stat from the number it returns, so the readout and
 * its bar cannot drift apart — they are not two animations being kept in
 * step, they are one value rendered twice in the same frame.
 *
 * Reduced motion: index.css switches `view-enter` and `scanline` off under
 * `prefers-reduced-motion: reduce`. A JS tween can't be disabled by that CSS
 * rule, so this reads the same media query and lands on the final value
 * immediately — the same end state the CSS rule produces for the animations
 * that can express it declaratively.
 */
import { useEffect, useRef, useState } from 'react'

/** Long enough to read as counting, short enough not to delay the number. */
export const COUNT_UP_MS = 600

/** Decelerating ease: quick off the mark, settles gently onto the value. */
export function easeOutCubic(t) {
  const clamped = Math.min(Math.max(t, 0), 1)
  return 1 - (1 - clamped) ** 3
}

/** Pure tween step, kept separate from React so it can be tested directly. */
export function tweenValue(from, to, progress) {
  return from + (to - from) * easeOutCubic(progress)
}

export function prefersReducedMotion() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    // Older engines throw on an unsupported query rather than returning false.
    return false
  }
}

const toFinite = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0)

/**
 * Animate towards `target`, starting from whatever is currently on screen — so
 * a first render counts up from 0, and a value that changes later counts from
 * the number the viewer was already looking at rather than snapping to 0.
 *
 * `duration <= 0` (and reduced motion) skip the tween entirely, including the
 * initial state, so there is no frame of 0 before the real value appears.
 */
export function useCountUp(target, { duration = COUNT_UP_MS } = {}) {
  const to = toFinite(target)
  const instant = duration <= 0 || prefersReducedMotion()

  const [value, setValue] = useState(() => (instant ? to : 0))

  // Read at effect time, not captured at render time, so a target that changes
  // mid-tween continues from the frame actually on screen.
  const valueRef = useRef(value)
  valueRef.current = value

  useEffect(() => {
    if (instant) {
      setValue(to)
      return undefined
    }
    const from = valueRef.current
    if (from === to) return undefined

    let raf = 0
    let startedAt = null
    const step = (now) => {
      if (startedAt === null) startedAt = now
      const progress = (now - startedAt) / duration
      if (progress >= 1) {
        setValue(to) // land exactly on the value, never an eased approximation
        return
      }
      setValue(tweenValue(from, to, progress))
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [to, duration, instant])

  return value
}
