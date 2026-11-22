/**
 * Announces price alerts the server saw reached (upgrade plan, Feature 4): a notice in
 * the corner, a short tone, and a desktop notification when this browser allows them.
 * Asks every 10 s while the tab is visible; events that fired while the app was closed
 * are announced on the next visit (lib/alertEvents.ts takeNew).
 */
import { useEffect, useState } from "react"

import { api } from "@/lib/api"
import { alertText, seen, takeNew, type AlertEvent } from "@/lib/alertEvents"

const POLL_MS = 10_000

function tone() {
  try {                                           // blocked until the page has been clicked; then fine
    const ctx = new AudioContext()
    const o = ctx.createOscillator(), g = ctx.createGain()
    o.frequency.value = 880; g.gain.value = 0.08
    o.connect(g).connect(ctx.destination)
    o.start(); o.stop(ctx.currentTime + 0.25)
  } catch { /* no audio: the notice still shows */ }
}

const canNotify = () => typeof Notification !== "undefined"

export function AlertNotifier() {
  const [shown, setShown] = useState<AlertEvent[]>([])
  const [perm, setPerm] = useState(() => (canNotify() ? Notification.permission : "denied"))

  useEffect(() => {
    let stop = false
    const tick = async () => {
      if (document.hidden) return
      try {
        const events = await api.getAlertEvents(seen() ?? 0)
        if (stop) return                          // unmounted meanwhile: leave them for the next mount
        const fresh = takeNew(events)             // marks them seen, so only once they are shown
        if (!fresh.length) return
        setShown((s) => [...s, ...fresh].slice(-5))
        tone()
        if (canNotify() && Notification.permission === "granted") {
          for (const e of fresh) new Notification(e.direction === "condition" ? "Condition alert" : "Price alert", { body: alertText(e), tag: `alert-${e.id}` })
        }
      } catch { /* server unreachable: try again next time */ }
    }
    void tick()
    const timer = setInterval(() => void tick(), POLL_MS)
    return () => { stop = true; clearInterval(timer) }
  }, [])

  if (!shown.length) return null
  return (
    <div className="fixed bottom-12 right-4 z-50 flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="assertive">
      {shown.map((e) => (
        <div key={e.id} role="alert"
             className="rounded-lg border border-amber-400/50 bg-[var(--surface-1)] px-3 py-2 text-sm shadow-xl">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-amber-600 dark:text-amber-300">
                {e.direction === "condition" ? "Condition alert" : "Price alert"}</div>
              <div className="mt-0.5 text-foreground">{alertText(e)}</div>
            </div>
            <button type="button" aria-label="Dismiss alert" className="text-muted-foreground hover:text-foreground"
                    onClick={() => setShown((s) => s.filter((x) => x.id !== e.id))}>x</button>
          </div>
          {perm === "default" && (
            <button type="button" className="mt-1.5 text-xs underline underline-offset-2 text-muted-foreground hover:text-foreground"
                    onClick={() => void Notification.requestPermission().then(setPerm)}>
              Also show alerts as desktop notifications
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
