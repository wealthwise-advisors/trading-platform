/**
 * Account settings: who you are signed in as, whether your address is
 * confirmed, and the way to close the account.
 *
 * There was previously nowhere in the application to manage an account at all.
 * This is deliberately small -- a dialog reusing the existing primitives, not a
 * new page or a new route -- because the product's navigation is a three-way
 * page switch and adding a fourth destination for one panel would change the
 * shape of the app to carry it.
 */
import { useEffect, useState } from "react"
import { api, auth, SIGN_IN_PAGE, type Me } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type Close =
  | { phase: "idle" }
  | { phase: "closing" }
  | { phase: "failed"; message: string }

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 border-b border-white/8 last:border-0">
      <span className="text-xs uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground text-right break-words min-w-0">{children}</span>
    </div>
  )
}

/**
 * A bug report with the boring parts already answered.
 *
 * mailto: rather than a form and an endpoint. A form would mean a new public
 * route, spam handling and somewhere to put the reports -- real work to build
 * and to operate -- when the operator's address is already published in
 * help.html and the privacy policy. This just stops every report from starting
 * with three rounds of "which version, which browser".
 *
 * Nothing personal is included beyond what the reporter's own mail client
 * attaches: no username, no session, no page contents.
 */
function bugReportHref(build: { version: string; commit: string } | null): string {
  const body = [
    "What I did:",
    "",
    "What I expected:",
    "",
    "What happened instead:",
    "",
    "---",
    `Build: ${build ? `${build.version} (${build.commit.slice(0, 7)})` : "unknown"}`,
    `Browser: ${typeof navigator === "undefined" ? "unknown" : navigator.userAgent}`,
    `Page: ${typeof window === "undefined" ? "unknown" : window.location.pathname}`,
    `When: ${new Date().toISOString()}`,
  ].join("\n")
  return `mailto:snandepu9@gmail.com?subject=${encodeURIComponent("AutoTrader — problem report")}&body=${encodeURIComponent(body)}`
}


export function AccountSettings({ user }: { user: Me }) {
  const [open, setOpen] = useState(false)
  const [armed, setArmed] = useState(false)
  const [confirm, setConfirm] = useState("")
  const [password, setPassword] = useState("")
  const [state, setState] = useState<Close>({ phase: "idle" })
  //: Which build this is. Fetched when the dialog opens rather than at app
  //: start, so the dashboard does not pay for a request nobody has asked for.
  const [build, setBuild] = useState<{ version: string; commit: string } | null>(null)

  useEffect(() => {
    if (!open || build) return
    let alive = true
    api.version()
      .then((v) => { if (alive) setBuild({ version: v.version, commit: v.commit }) })
      .catch(() => { /* a missing version line must not break the dialog */ })
    return () => { alive = false }
  }, [open, build])

  // The server requires the username typed exactly and re-checks the password
  // itself. Mirroring the first check here is not the security control -- it
  // keeps the button honest about whether pressing it will do anything.
  const typedOk = confirm.trim().toLowerCase() === user.username.toLowerCase()
  const busy = state.phase === "closing"

  async function closeAccount() {
    if (busy) return                       // guard, not just a disabled button
    setState({ phase: "closing" })
    try {
      await auth.closeAccount(confirm.trim(), password)
      // Straight out. The session is already revoked server-side and the
      // cookie cleared, so anything that re-renders from here would render
      // for an account that no longer exists.
      window.location.assign(`${SIGN_IN_PAGE}?reason=account_closed`)
    } catch (e) {
      setState({ phase: "failed", message: (e as Error)?.message ?? "Could not close the account." })
    }
  }

  function reset() {
    setArmed(false)
    setConfirm("")
    setPassword("")
    setState({ phase: "idle" })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()               // never reopen mid-confirmation
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" title="Account settings">
          Account
        </Button>
      </DialogTrigger>

      <DialogContent
        title="Account"
        description="Your account details and the option to close it."
        className="max-w-lg"
      >
        <div className="px-5 py-4 space-y-5 overflow-y-auto">
          <div>
            <Row label="Username">{user.username}</Row>
            {user.full_name && <Row label="Name">{user.full_name}</Row>}
            <Row label="Email">{user.email || <span className="text-muted-foreground">none on file</span>}</Row>
            <Row label="Address confirmed">
              {user.email_verified ? (
                <span className="text-emerald-400">Confirmed</span>
              ) : (
                <span className="text-amber-400">Not confirmed</span>
              )}
            </Row>
            {user.country && <Row label="Country">{user.country}</Row>}
          </div>

          {!user.email_verified && user.email && (
            <p className="text-xs text-muted-foreground">
              Your address has not been confirmed yet. Use the link we emailed
              you, or sign out and back in to request another.
            </p>
          )}

          <div className="pt-1 border-t border-white/8">
            <h3 className="text-sm font-semibold text-foreground mt-4">Something wrong?</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Report it with the details already filled in — which build you are
              on, and what browser. That is most of what makes a bug
              reproducible.
            </p>
            <Button asChild variant="outline" size="sm" className="mt-3">
              <a href={bugReportHref(build)}>Report a problem</a>
            </Button>
            {/* The build line, shown whether or not anyone clicks the button:
                "which version are you on" is the first question every support
                thread asks, and until now the answer lived only in an API
                endpoint nothing surfaced. */}
            <p className="mt-3 text-[11px] font-mono text-muted-foreground/70">
              {build
                ? `AutoTrader ${build.version} · ${build.commit.slice(0, 7)}`
                : "AutoTrader · checking build…"}
            </p>
          </div>

          <div className="pt-1 border-t border-white/8">
            <h3 className="text-sm font-semibold text-foreground mt-4">Your data</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Download everything this account holds — your details, saved
              configurations, backtests and trades — as a JSON file. Passwords
              and session keys are never included.
            </p>
            {/* A plain link, not a fetch: the browser handles the download and
                the Content-Disposition header names the file. Routing this
                through JavaScript would mean holding the whole export in
                memory to hand it straight back to the browser. */}
            <Button asChild variant="outline" size="sm" className="mt-3">
              <a href={auth.exportUrl()} download>Download my data</a>
            </Button>
          </div>

          <div className="pt-1 border-t border-white/8">
            <h3 className="text-sm font-semibold text-foreground mt-4">Close this account</h3>
            <p className="text-xs text-muted-foreground mt-1">
              This deletes your account, your saved backtests and their trades,
              and signs you out everywhere. It cannot be undone and there is no
              way to recover the data afterwards.
            </p>

            {!armed ? (
              <Button
                variant="outline"
                size="sm"
                className="mt-3 text-destructive border-destructive/40 hover:bg-destructive/10"
                onClick={() => setArmed(true)}
              >
                Close account…
              </Button>
            ) : (
              <div className="mt-3 space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="close-confirm">
                    Type <span className="font-mono text-foreground">{user.username}</span> to confirm
                  </Label>
                  <Input
                    id="close-confirm"
                    value={confirm}
                    autoComplete="off"
                    disabled={busy}
                    onChange={(e) => setConfirm(e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="close-password">Your password</Label>
                  <Input
                    id="close-password"
                    type="password"
                    value={password}
                    autoComplete="current-password"
                    disabled={busy}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  {/* Accounts created through Google, LinkedIn, GitHub or X
                      have no password to re-enter; the typed username is the
                      confirmation in that case and the server accepts it. */}
                  <p className="text-xs text-muted-foreground">
                    Leave blank if you only ever sign in with Google, LinkedIn,
                    GitHub or X.
                  </p>
                </div>

                {state.phase === "failed" && (
                  <p role="alert" className="text-sm text-destructive">{state.message}</p>
                )}

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive border-destructive/40 hover:bg-destructive/10"
                    disabled={!typedOk || busy}
                    onClick={closeAccount}
                  >
                    {busy ? "Closing…" : "Close my account permanently"}
                  </Button>
                  <Button variant="ghost" size="sm" disabled={busy} onClick={reset}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
