/**
 * A small circled "i" that explains one control, on click.
 *
 * WHY A BUTTON AND NOT A PARAGRAPH. The session cards used to carry their
 * explanation as permanently visible body text -- three lines under GLOBEX,
 * two under RTH. That text is worth reading exactly once, while you are
 * deciding, and after that it is a paragraph standing between you and the
 * control it describes. Behind a click it stays available and stops costing
 * anything.
 *
 * WHY NOT A `title` ATTRIBUTE, WHICH IS WHAT THIS REPLACED IN PLACES. A native
 * tooltip needs a hover, waits about a second, cannot be reached from a
 * keyboard on most browsers, and never appears on a touch screen. This opens
 * on click, from a real button, and closes on Escape, on a second click, or on
 * a click anywhere outside.
 *
 * THE ICON IS A LOWERCASE "i" IN A CIRCLE, deliberately. An eye means "show or
 * hide this thing"; an "i" means "here is what this thing is". They are
 * different promises, and the eye was making the wrong one.
 */

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react"
import type { ReactNode } from "react"
import { Info } from "lucide-react"

export function InfoDot({
  label, children, className = "", align = "right",
}: {
  /** What is being explained. Used for the accessible name: "About RSI Overbought". */
  label: string
  children: ReactNode
  className?: string
  /** Which edge the panel hangs from before it is clamped to the viewport. */
  align?: "left" | "right"
}) {
  const [open, setOpen] = useState(false)
  const [nudge, setNudge] = useState(0)
  const wrap = useRef<HTMLSpanElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const id = useId()

  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false) }
    document.addEventListener("mousedown", away)
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("mousedown", away)
      document.removeEventListener("keydown", esc)
    }
  }, [open])

  // Keep the panel on screen. These sit in the last column of a grid and near
  // the right edge of the page, so the natural position pushes a 260px panel
  // past the window more often than not. Measured and shifted rather than
  // guessed at with a breakpoint, because which cards overhang depends on the
  // window width, not on the card.
  useLayoutEffect(() => {
    if (!open) { setNudge(0); return }
    const el = panel.current
    if (!el) return
    setNudge(0)
    const r = el.getBoundingClientRect()
    const pad = 8
    if (r.right > window.innerWidth - pad) setNudge(window.innerWidth - pad - r.right)
    else if (r.left < pad) setNudge(pad - r.left)
  }, [open])

  return (
    <span ref={wrap} className={`relative inline-flex shrink-0 ${className}`}>
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls={open ? id : undefined}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v) }}
        className={`info-dot${open ? " info-dot-on" : ""}`}
      >
        <Info size={13} strokeWidth={2.2} aria-hidden />
      </button>
      {open && (
        <div
          ref={panel}
          id={id}
          role="dialog"
          aria-label={label}
          style={{ transform: `translateX(${nudge}px)` }}
          className={`info-pop ${align === "right" ? "right-0" : "left-0"}`}
        >
          <p className="info-pop-title">{label}</p>
          <div className="info-pop-body">{children}</div>
        </div>
      )}
    </span>
  )
}
