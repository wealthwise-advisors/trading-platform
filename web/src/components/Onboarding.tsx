/**
 * The introduction a new account sees once.
 *
 * "Once" is the design problem, and the reason the flag is stored on the
 * ACCOUNT (users.onboarded_at) rather than in localStorage: in the browser it
 * means the wrong thing in both directions -- the welcome reappears on every
 * new machine someone signs in from, and disappears for good the moment site
 * data is cleared, on a different account even.
 *
 * THREE STEPS, NOT A LIST
 * A list of three bullets is read as one glance and remembered as none. One
 * step at a time gives each feature the whole card, and the progress dots make
 * the length of the thing obvious up front -- nobody abandons a three-step
 * screen, they abandon one of unknown depth.
 *
 * ABOUT THE MOTION
 * Each illustration demonstrates the feature it describes: the equity curve
 * draws itself, the candles arrive one at a time, the rows lift off the page.
 * That is motion doing a job. The pointer-tilt tried on the sign-in card was
 * the other kind and was rightly thrown out -- nothing here reacts to the
 * cursor, and everything stops under prefers-reduced-motion.
 *
 * It never blocks. Skip is present on every step, Escape works throughout, and
 * a failed request still lets the person through -- see finish().
 */
import { useCallback, useEffect, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { ArrowLeft, ArrowRight, BarChart3, Download, Zap } from "lucide-react"

import brandWordmark from "@/assets/brand-wordmark.png"
import { auth, type Me } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { BacktestArt, ExportArt, ReplayArt } from "@/components/onboarding-art"

const STEPS = [
  {
    icon: BarChart3,
    art: BacktestArt,
    eyebrow: "Step one",
    title: "Backtest a strategy",
    body: "Pick an instrument, a strategy and a date range in the panel on the left, then run it. You get the equity curve, every trade, and the chart with entries and exits marked.",
    aside: "ES · NQ · MES · CL and more, from synthetic data to your own CSVs.",
  },
  {
    icon: Zap,
    art: ReplayArt,
    eyebrow: "Step two",
    title: "Watch it trade, bar by bar",
    body: "Market Grid walks the same strategy through the market one bar at a time, so you can see when a signal fires rather than only what it scored at the end.",
    aside: "Pause, step, and follow live — the same engine as the backtest.",
  },
  {
    icon: Download,
    art: ExportArt,
    eyebrow: "Step three",
    title: "Take the data with you",
    body: "Export the bars behind any run as CSV or Excel, or the whole result as a self-contained HTML report that opens on any machine.",
    aside: "Your saved setups follow your account, not this browser.",
  },
] as const

export function Onboarding({ user, onDone }: { user: Me; onDone: () => void }) {
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const still = useReducedMotion()
  const last = step === STEPS.length - 1

  const finish = useCallback(async () => {
    if (saving) return                       // guard, not just a disabled button
    setSaving(true)
    try {
      await auth.finishOnboarding()
    } catch {
      // Deliberately swallowed. If recording the flag fails, the right outcome
      // is still to let the person into the product -- they see this once more
      // next time, which is a far smaller cost than being held at a welcome
      // screen by a failed request.
    } finally {
      onDone()
    }
  }, [saving, onDone])

  const next = useCallback(() => {
    if (last) { void finish() } else { setStep((s) => s + 1) }
  }, [last, finish])
  const back = useCallback(() => setStep((s) => Math.max(0, s - 1)), [])

  /* Arrow keys to move, Escape to leave. A screen with Next and Back that only
     answers the mouse is a screen a keyboard user has to tab around. */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") next()
      else if (e.key === "ArrowLeft") back()
      else if (e.key === "Escape") void finish()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [next, back, finish])

  const s = STEPS[step]
  const Icon = s.icon
  const Art = s.art
  const firstName = user.full_name ? user.full_name.split(" ")[0] : ""

  return (
    <div className="min-h-screen grid place-items-center bg-background p-5">
      <div className="w-full" style={{ maxWidth: 560 }}>
        <div className="flex items-center justify-between mb-6">
          <img src={brandWordmark} alt="AutoTrader" className="h-6 w-auto object-contain" />
          <Button variant="ghost" size="sm" onClick={finish} disabled={saving}>
            Skip
          </Button>
        </div>

        <div className="rounded-2xl border border-white/8 bg-card/80 backdrop-blur-sm
                        shadow-[0_24px_60px_-24px_rgba(0,0,0,.7)] overflow-hidden">
          <div className="px-6 pt-6 pb-2 bg-[linear-gradient(180deg,rgba(124,108,245,.08),transparent)]">
            {/* key={step} remounts the illustration, which is what replays its
                animation -- the drawing is the point, not the final frame. */}
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: still ? 0 : 0.18 }}
              >
                <Art />
              </motion.div>
            </AnimatePresence>
          </div>

          <div className="px-6 pb-6 pt-4">
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: still ? 0 : 14 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: still ? 0 : -14 }}
                transition={{ duration: still ? 0 : 0.22, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="grid place-items-center h-7 w-7 rounded-lg
                                   bg-primary/15 text-primary ring-1 ring-primary/25">
                    <Icon className="h-3.5 w-3.5" aria-hidden />
                  </span>
                  <span className="text-[11px] font-semibold uppercase tracking-[.14em]
                                   text-muted-foreground">
                    {s.eyebrow}
                  </span>
                </div>
                <h2 className="text-xl font-semibold text-foreground">{s.title}</h2>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
                <p className="mt-3 text-xs text-muted-foreground/70 border-l-2 border-primary/30 pl-3">
                  {s.aside}
                </p>
              </motion.div>
            </AnimatePresence>

            <div className="mt-6 flex items-center justify-between gap-3">
              {/* Progress. aria-hidden because the live region below says the
                  same thing in words -- a screen reader announcing three dots
                  is noise. */}
              <div className="flex items-center gap-1.5" aria-hidden>
                {STEPS.map((_, i) => (
                  <span
                    key={i}
                    className={
                      "h-1.5 rounded-full transition-all duration-300 " +
                      (i === step ? "w-6 bg-primary" : "w-1.5 bg-white/15")
                    }
                  />
                ))}
              </div>

              <div className="flex items-center gap-2">
                {step > 0 && (
                  <Button variant="outline" size="sm" onClick={back} disabled={saving}>
                    <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Back
                  </Button>
                )}
                <Button size="sm" onClick={next} disabled={saving}>
                  {saving ? "One moment…" : last ? "Get started" : "Next"}
                  {!last && <ArrowRight className="h-3.5 w-3.5" aria-hidden />}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <p className="mt-4 text-center text-xs text-muted-foreground/70">
          {firstName ? `Welcome, ${firstName}. ` : "Welcome. "}
          You will only see this once.
        </p>

        {/* The dots are decorative; this is what actually gets announced. */}
        <span role="status" aria-live="polite" className="sr-only">
          {`Step ${step + 1} of ${STEPS.length}: ${s.title}`}
        </span>
      </div>
    </div>
  )
}
