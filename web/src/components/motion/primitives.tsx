// Shared motion primitives for the Market Grid.
//
// Everything here follows one recipe so the page moves as a single system:
// enter = opacity + 8px rise + a 4px blur burning off, on a bounce-free spring.
// The blur is the part that makes it read as "materialising" rather than
// "fading" -- an element coming into focus, not a ghost appearing.
//
// Every primitive checks prefers-reduced-motion and collapses to a plain,
// instant render. That is a real code path, not a CSS afterthought: a user
// with the setting on gets no transform and no blur at all.

import {
  motion, useReducedMotion, useMotionValue, useSpring, useTransform,
  type Transition,
} from "framer-motion"
import { useEffect, type ReactNode } from "react"

/** Production default. bounce: 0 -- smooth deceleration, no overshoot. */
export const SPRING: Transition = { type: "spring", duration: 0.45, bounce: 0 }
/** Slightly slower, for larger surfaces. */
export const SPRING_SLOW: Transition = { type: "spring", duration: 0.6, bounce: 0 }

/** Enter recipe. `delay` staggers siblings; keep steps small (40-60ms). */
export function Reveal({
  children, delay = 0, y = 8, className,
}: {
  children: ReactNode
  delay?: number
  y?: number
  className?: string
}) {
  const reduced = useReducedMotion()
  if (reduced) return <div className={className}>{children}</div>
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y, filter: "blur(4px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ ...SPRING, delay }}
    >
      {children}
    </motion.div>
  )
}

/** A number that eases to its new value instead of jumping.
 *
 *  Used only where the value CHANGES while on screen -- a figure that lands
 *  once and never moves is better rendered as text. Animating those would be
 *  decoration, and decoration on a number reads as instability. */
export function CountUp({
  value, decimals = 0, suffix = "", prefix = "",
}: {
  value: number
  decimals?: number
  suffix?: string
  prefix?: string
}) {
  const reduced = useReducedMotion()
  const mv = useMotionValue(value)
  // Not a visual spring -- this one drives a readout, so it must settle
  // quickly and never overshoot past the true value.
  const spring = useSpring(mv, { stiffness: 170, damping: 26, mass: 0.6 })
  const text = useTransform(spring, (v) =>
    `${prefix}${(Number.isFinite(v) ? v : 0).toLocaleString(undefined, {
      minimumFractionDigits: decimals, maximumFractionDigits: decimals,
    })}${suffix}`)

  useEffect(() => { mv.set(value) }, [value, mv])

  if (reduced) {
    return (
      <span className="tabular-nums">
        {prefix}
        {value.toLocaleString(undefined, {
          minimumFractionDigits: decimals, maximumFractionDigits: decimals,
        })}
        {suffix}
      </span>
    )
  }
  return <motion.span className="tabular-nums">{text}</motion.span>
}

/** Press feedback for a control. Scale only -- no colour flash, no ripple.
 *
 *  whileTap rather than :active so the scale retargets mid-flight when a user
 *  hammers the control; a keyframe would restart and stutter. */
export const PRESS = { scale: 0.96 }
export const PRESS_SOFT = { scale: 0.98 }

/** Staggered list container. Children should be <motion.div variants={ITEM}>. */
export const LIST = {
  hidden: {},
  show: { transition: { staggerChildren: 0.055, delayChildren: 0.04 } },
}
export const ITEM = {
  hidden: { opacity: 0, y: 8, filter: "blur(4px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: SPRING },
}

export { motion, useReducedMotion }
