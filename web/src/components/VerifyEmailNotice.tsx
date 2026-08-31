/**
 * Shown instead of the dashboard while an account's address is unproved.
 *
 * Only ever rendered when the server says `verification_required`, which it
 * does not say unless confirmation mail can actually be delivered -- see
 * api/auth.py's verification_enforced(). That coupling is what stops this
 * screen from becoming a dead end: it is never shown to someone whose
 * confirmation link was never sent and never will be.
 *
 * It offers a way forward and a way out. A screen that blocks the app with
 * neither is a lockout, not a gate.
 */
import { useState } from "react"
import { auth, SIGN_IN_PAGE, type Me } from "@/lib/api"
import { Button } from "@/components/ui/button"

type Send =
  | { phase: "idle" }
  | { phase: "sending" }
  | { phase: "sent"; detail: string }
  | { phase: "failed"; detail: string }

export function VerifyEmailNotice({ user }: { user: Me }) {
  const [send, setSend] = useState<Send>({ phase: "idle" })

  async function resend() {
    // Guarded rather than merely disabled: the button is disabled below while
    // this runs, but a double-fired event or a keyboard repeat can still land
    // twice, and each landing sends real mail from a rate-limited sender.
    if (send.phase === "sending") return
    setSend({ phase: "sending" })
    try {
      const res = await auth.resendVerification()
      setSend({
        phase: "sent",
        detail: res.detail ?? "Sent. Check your inbox and spam folder.",
      })
    } catch (e) {
      setSend({ phase: "failed", detail: (e as Error)?.message ?? "Could not send." })
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-background p-6">
      <div className="w-full max-w-md space-y-5">
        <div className="space-y-2">
          <h1 className="text-lg font-semibold text-foreground">
            Confirm your email address
          </h1>
          <p className="text-sm text-muted-foreground">
            We sent a link to{" "}
            <span className="font-medium text-foreground break-words">{user.email}</span>{" "}
            when you registered. Open it to finish setting up your account.
          </p>
          <p className="text-sm text-muted-foreground">
            The link works once and expires 24 hours after it is sent. If yours
            has expired, send another below.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={resend} disabled={send.phase === "sending"}>
            {send.phase === "sending" ? "Sending…" : "Send another link"}
          </Button>
          {/* The way out. Without it, someone signed in to the wrong account
              has no route to the right one -- the dashboard is blocked and the
              only sign-out button lives inside it. */}
          <Button
            variant="outline"
            onClick={async () => {
              await auth.logout()
              window.location.assign(SIGN_IN_PAGE)
            }}
          >
            Sign out
          </Button>
          <Button variant="ghost" onClick={() => window.location.reload()}>
            I have confirmed it
          </Button>
        </div>

        {send.phase !== "idle" && send.phase !== "sending" && (
          <p
            role="status"
            aria-live="polite"
            className={
              send.phase === "sent"
                ? "text-sm text-muted-foreground"
                : "text-sm text-destructive"
            }
          >
            {send.detail}
          </p>
        )}
      </div>
    </div>
  )
}
