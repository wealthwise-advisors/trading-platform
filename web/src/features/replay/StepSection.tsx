// A numbered block of the setup form.
//
// The setup used to be one undivided card: eleven controls, no reading order,
// and no way to tell how far through you were. Numbering it turns the same
// fields into a sequence, and the badge answers "have I done this one?"
// without a separate progress widget.
//
// The badge's tick is the only motion here, and it fires on a real state
// change (the step became satisfiable), not on mount -- so it means something
// every time it happens.

import { Check } from "lucide-react"
import { AnimatePresence } from "framer-motion"
import type { ReactNode } from "react"
import { Reveal, SPRING, motion, useReducedMotion } from "@/components/motion/primitives"

export function StepSection({
  n, title, hint, Icon, done = false, delay = 0, children,
}: {
  n: number
  title: string
  /** Right-aligned summary, rendered as a chip. */
  hint?: ReactNode
  /** Replaces the number/tick badge — for sections that are not a "step". */
  Icon?: typeof Check
  /** Drives the badge. True once this step has a usable value. */
  done?: boolean
  delay?: number
  children: ReactNode
}) {
  const reduced = useReducedMotion()

  return (
    <Reveal delay={delay}>
      <section className="rounded-2xl border border-white/8 bg-[#0a1120] overflow-hidden">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3
                           border-b border-white/8 bg-[#0c1526]">
          {Icon ? (
            <span aria-hidden className="grid place-items-center h-7 w-7 rounded-lg
                                         bg-violet-500/12 text-violet-300 ring-1 ring-violet-400/25">
              <Icon size={15} strokeWidth={2.2} />
            </span>
          ) : (
            <span
              aria-hidden
              className={`relative grid place-items-center h-7 w-7 rounded-full text-[11px]
                          font-bold transition-colors duration-300
                          ${done
                            ? "bg-violet-500/12 text-violet-300 ring-1 ring-violet-400/35"
                            : "bg-white/6 text-slate-400 ring-1 ring-white/10"}`}
            >
              <AnimatePresence mode="wait" initial={false}>
                {done ? (
                  <motion.span
                    key="done"
                    initial={reduced ? false : { opacity: 0, scale: 0.7, filter: "blur(3px)" }}
                    animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                    exit={reduced ? undefined : { opacity: 0, scale: 0.9 }}
                    transition={reduced ? { duration: 0 } : SPRING}
                  >
                    <Check size={14} strokeWidth={3} />
                  </motion.span>
                ) : (
                  <motion.span
                    key="num"
                    initial={reduced ? false : { opacity: 0, scale: 0.7 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={reduced ? undefined : { opacity: 0, scale: 0.9 }}
                    transition={reduced ? { duration: 0 } : SPRING}
                  >
                    {n}
                  </motion.span>
                )}
              </AnimatePresence>
            </span>
          )}

          <h3 className="text-[13px] font-bold uppercase tracking-[0.11em] text-slate-100">
            {title}
          </h3>

          {hint && (
            <span className="ml-auto flex items-center gap-2 rounded-lg border border-violet-400/20
                             bg-violet-500/[0.07] px-3 py-1.5 text-[12px] font-semibold text-slate-300">
              {hint}
            </span>
          )}
        </header>

        <div className="p-4">{children}</div>
      </section>
    </Reveal>
  )
}
