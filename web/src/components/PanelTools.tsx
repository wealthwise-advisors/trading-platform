/**
 * The icon controls at the right edge of a data panel's header.
 *
 * The full-screen state lives in lib/usePanelFullscreen -- a file that exports
 * both components and a hook loses fast refresh.
 */

import { Maximize2, Minimize2 } from "lucide-react"

/** One square icon button, sized to sit inside a panel header without
 *  changing its height. */
export function PanelToolButton({
  label, onClick, pressed, children,
}: {
  label: string
  onClick: () => void
  /** Present for toggles; omitted for plain actions. */
  pressed?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className="grid h-6 w-6 place-items-center rounded border
                 border-[color:var(--hairline-mid)] bg-[color:var(--raise-2)]
                 text-muted-foreground hover:bg-[color:var(--raise-4)] hover:text-foreground"
    >
      {children}
    </button>
  )
}

export function FullscreenButton({ isFull, onToggle, what }: {
  isFull: boolean
  onToggle: () => void
  /** Named so three of these on one page do not all announce "Full screen". */
  what: string
}) {
  return (
    <PanelToolButton
      label={isFull ? `Exit full screen — ${what}` : `Full screen — ${what}`}
      pressed={isFull}
      onClick={onToggle}
    >
      {isFull ? <Minimize2 size={12} strokeWidth={2.2} />
              : <Maximize2 size={12} strokeWidth={2.2} />}
    </PanelToolButton>
  )
}
