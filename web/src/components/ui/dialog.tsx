// Modal dialog, built on the same unified `radix-ui` package the Slider and
// Select already use, so there is one primitive source in the bundle rather
// than a second copy of Radix pulled in per component.
//
// Enter/exit motion is CSS keyed on Radix's own data-state, not Framer: the
// overlay and panel must finish animating out BEFORE Radix unmounts them, and
// data-state gives that for free where an AnimatePresence around a portal
// needs wiring to get right.

import { Dialog as DialogPrimitive } from "radix-ui"
import { X } from "lucide-react"
import type { ComponentProps, ReactNode } from "react"

import { cn } from "@/lib/utils"

const Dialog = DialogPrimitive.Root
const DialogTrigger = DialogPrimitive.Trigger
const DialogClose = DialogPrimitive.Close

function DialogContent({
  className, children, title, description, onClose, ...props
}: ComponentProps<typeof DialogPrimitive.Content> & {
  /** Rendered in the header AND used as the accessible name. */
  title: ReactNode
  /** Screen-reader description. Visually hidden. */
  description?: string
  onClose?: () => void
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="dlg-overlay" />
      <DialogPrimitive.Content
        className={cn("dlg-panel", className)}
        {...props}
      >
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/8 shrink-0">
          <DialogPrimitive.Title asChild>
            <h2 className="text-[14px] font-bold uppercase tracking-[0.11em] text-slate-100">
              {title}
            </h2>
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            {description ?? "Dialog"}
          </DialogPrimitive.Description>
          <DialogPrimitive.Close
            onClick={onClose}
            aria-label="Close"
            className="ml-auto grid place-items-center h-9 w-9 rounded-lg border border-white/10
                       bg-white/[0.03] text-slate-400 transition-colors duration-200
                       hover:bg-white/8 hover:text-slate-100
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
          >
            <X size={17} strokeWidth={2.2} />
          </DialogPrimitive.Close>
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

export { Dialog, DialogTrigger, DialogClose, DialogContent }
