/**
 * Loads the workspace account, then renders the app.
 *
 * Replaces AuthGate, which decided between the dashboard and a sign-in page.
 * Sign-in was removed on 2026-10-16 -- the app opens straight from its link --
 * so there is no signed-out state left to decide about. What remains:
 *
 *   loading     one request for the workspace account (the header shows its
 *               initials; the introduction keys on it)
 *   onboarding  the first-run introduction, until it is dismissed
 *   error       the server could not be reached, with a way to retry --
 *               never a blank page
 */
import { useEffect, useState, type ReactNode } from "react"

import { auth, type Me } from "@/lib/api"
import { Onboarding } from "@/components/Onboarding"

type State =
  | { phase: "loading" }
  | { phase: "onboarding"; user: Me }
  | { phase: "ready"; user: Me }
  | { phase: "error"; message: string }

export function WorkspaceLoader({ children }: { children: (user: Me) => ReactNode }) {
  const [state, setState] = useState<State>({ phase: "loading" })

  useEffect(() => {
    let alive = true
    auth
      .whoami()
      .then((user) => {
        if (!alive) return
        // ?tour=1 replays the introduction after it has been dismissed. The
        // flag lives on the account, so without this there is no way back to
        // a screen worth being able to re-read.
        const replay = new URLSearchParams(window.location.search).get("tour") === "1"
        setState(replay || !user.onboarded ? { phase: "onboarding", user } : { phase: "ready", user })
      })
      .catch((e) => {
        if (alive) setState({ phase: "error", message: String(e?.message ?? e) })
      })
    return () => { alive = false }
  }, [])

  if (state.phase === "loading") {
    return (
      <div className="min-h-screen grid place-items-center bg-background text-muted-foreground">
        <div className="flex items-center gap-3 text-sm">
          <span className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          Loading…
        </div>
      </div>
    )
  }

  if (state.phase === "onboarding") {
    return (
      <Onboarding
        user={state.user}
        onDone={() => {
          // Drop ?tour=1 on the way out, so a refresh does not reopen it and
          // the URL someone copies is not a permanent tour link.
          if (window.location.search.includes("tour=")) {
            window.history.replaceState({}, "", window.location.pathname)
          }
          setState({ phase: "ready", user: state.user })
        }}
      />
    )
  }

  if (state.phase === "error") {
    return (
      <div className="min-h-screen grid place-items-center bg-background p-6">
        <div className="max-w-md text-center space-y-3">
          <h1 className="text-lg font-semibold text-foreground">Cannot reach the server</h1>
          <p className="text-sm text-muted-foreground">{state.message}</p>
          <button className="text-sm text-primary underline" onClick={() => window.location.reload()}>
            Try again
          </button>
        </div>
      </div>
    )
  }

  return <>{children(state.user)}</>
}
