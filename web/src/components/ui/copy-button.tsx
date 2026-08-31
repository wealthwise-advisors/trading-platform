/**
 * Copy one string to the clipboard, and say so.
 *
 * Deliberately small and deliberately rare. A copy button earns its place next
 * to something a person would otherwise select by hand and get wrong -- a
 * wrapped URL, an id, a token. Sprinkling one beside every field turns a useful
 * affordance into visual noise, so this component exists once and is used where
 * that test is met.
 *
 * The confirmation is the button itself changing, not a toast: the feedback
 * belongs where the attention already is, and a floating notification for
 * "copied" is more interruption than the action deserves.
 */
import { useEffect, useRef, useState } from "react"
import { Check, Copy } from "lucide-react"

import { Button } from "@/components/ui/button"

export function CopyButton({
  value,
  label = "Copy to clipboard",
}: {
  value: string
  /** Accessible name. The button is icon-only, so this is its only name. */
  label?: string
}) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clearing on unmount matters here: the export URL rebuilds as the form
  // changes, so this button is remounted often, and a pending timeout firing
  // into a gone component is a React warning at best.
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      // navigator.clipboard is undefined on an insecure origin and can be
      // refused by permissions policy. Falling back keeps the button honest on
      // a plain-http deployment rather than silently doing nothing.
      const ta = document.createElement("textarea")
      ta.value = value
      ta.setAttribute("readonly", "")
      ta.style.position = "fixed"
      ta.style.opacity = "0"
      document.body.appendChild(ta)
      ta.select()
      try { document.execCommand("copy") } catch { /* nothing more to try */ }
      document.body.removeChild(ta)
    }
    setCopied(true)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopied(false), 1600)
  }

  return (
    <>
      <Button
        type="button"
        size="icon-sm"
        variant="secondary"
        onClick={copy}
        aria-label={label}
        title={label}
        className="shrink-0"
      >
        {copied
          ? <Check className="h-3.5 w-3.5 text-emerald-400" aria-hidden />
          : <Copy className="h-3.5 w-3.5" aria-hidden />}
      </Button>
      {/* Announced, not just drawn. The icon swap is invisible to a screen
          reader, so without this the action gives no feedback at all. */}
      <span role="status" aria-live="polite" className="sr-only">
        {copied ? "Copied to clipboard" : ""}
      </span>
    </>
  )
}
