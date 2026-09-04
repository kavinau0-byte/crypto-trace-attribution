import { useEffect, useState } from 'react'
import { Check, Copy } from 'lucide-react'

/** Copy-to-clipboard control. Falls back to a hidden textarea on non-secure origins. */
export default function CopyButton({ value, label = 'Copy', className = '' }) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return undefined
    const t = setTimeout(() => setCopied(false), 1400)
    return () => clearTimeout(t)
  }, [copied])

  async function copy(event) {
    event.preventDefault()
    event.stopPropagation()
    const text = String(value ?? '')
    if (!text) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const el = document.createElement('textarea')
        el.value = text
        el.setAttribute('readonly', '')
        el.style.position = 'fixed'
        el.style.opacity = '0'
        document.body.appendChild(el)
        el.select()
        document.execCommand('copy')
        document.body.removeChild(el)
      }
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      title={copied ? 'Copied' : label}
      aria-label={copied ? 'Copied' : label}
      className={`inline-flex shrink-0 items-center justify-center rounded-sm p-1 text-ink-faint transition-colors hover:bg-line hover:text-accent ${className}`}
    >
      {copied ? (
        <Check size={13} strokeWidth={2.5} className="text-match" />
      ) : (
        <Copy size={13} strokeWidth={2} />
      )}
    </button>
  )
}
