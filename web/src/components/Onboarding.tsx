/**
 * The introduction a new account sees once.
 *
 * "Once" is the whole design problem. The completion flag is stored on the
 * ACCOUNT (users.onboarded_at), not in localStorage, because in the browser it
 * means the wrong thing in both directions: the welcome screen reappears on
 * every new machine someone signs in from, and it disappears permanently the
 * moment they clear site data — on a different account, even.
 *
 * It is skippable from the first frame and never blocks anything. Dismissing it
 * and finishing it record the same flag, deliberately: the question the flag
 * answers is "has this person been offered the introduction", not "did they
 * read it".
 */
import { useState } from "react"
import { auth, type Me } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { BarChart3, Zap, Download } from "lucide-react"

const STEPS = [
  {
    icon: BarChart3,
    title: "Backtest a strategy",
    body: "Pick an instrument, a strategy and a date range in the panel on the left, then run it. " +
          "You get the equity curve, every trade, and the chart with entries and exits marked.",
  },
  {
    icon: Zap,
    title: "Watch it trade, bar by bar",
    body: "Live Replay walks the same strategy through the market one bar at a time, " +
          "so you can see when a signal fires rather than only what it scored.",
  },
  {
    icon: Download,
    title: "Take the data with you",
    body: "Export the bars behind any run as CSV, or the whole result as a self-contained " +
          "HTML report that opens on any machine.",
  },
] as const

export function Onboarding({ user, onDone }: { user: Me; onDone: () => void }) {
  const [saving, setSaving] = useState(false)

  async function finish() {
    if (saving) return                       // guard as well as disable
    setSaving(true)
    try {
      await auth.finishOnboarding()
    } catch {
      // Deliberately swallowed. If recording the flag fails, the right
      // outcome is still to let the person into the product -- they will see
      // this once more next time, which is a far smaller cost than being held
      // at a welcome screen by a failed request.
    } finally {
      onDone()
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-background p-6">
      <div className="w-full max-w-lg space-y-6">
        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-foreground">
            Welcome to AutoTrader{user.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}
          </h1>
          <p className="text-sm text-muted-foreground">
            Three things it does. This takes about twenty seconds and you will
            not see it again.
          </p>
        </div>

        <ol className="space-y-4">
          {STEPS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex gap-3">
              <span
                aria-hidden
                className="mt-0.5 grid place-items-center h-8 w-8 shrink-0 rounded-lg border border-white/10 bg-white/[0.03] text-primary"
              >
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-foreground">{title}</h2>
                <p className="text-sm text-muted-foreground">{body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="flex items-center gap-2">
          <Button onClick={finish} disabled={saving}>
            {saving ? "One moment…" : "Get started"}
          </Button>
          <Button variant="ghost" onClick={finish} disabled={saving}>
            Skip
          </Button>
        </div>
      </div>
    </div>
  )
}
