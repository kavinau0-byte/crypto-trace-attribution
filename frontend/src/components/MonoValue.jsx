import CopyButton from './CopyButton'
import { truncateMiddle } from '../lib/format'

/**
 * A Bitcoin address or transaction hash. Monospace, middle-truncated, with the
 * full string available on hover and one click away from the clipboard.
 */
export default function MonoValue({
  value,
  head = 10,
  tail = 8,
  copy = true,
  full = false,
  className = '',
  tone = 'default',
}) {
  const text = String(value ?? '')
  if (!text) return <span className="text-ink-faint">—</span>

  const tones = {
    default: 'text-ink',
    dim: 'text-ink-dim',
    accent: 'text-accent',
  }

  return (
    <span className={`inline-flex min-w-0 items-center gap-1.5 ${className}`}>
      <span
        title={text}
        className={`data truncate text-[13px] leading-relaxed ${tones[tone] || tones.default}`}
      >
        {full ? text : truncateMiddle(text, head, tail)}
      </span>
      {copy ? <CopyButton value={text} label="Copy to clipboard" /> : null}
    </span>
  )
}
