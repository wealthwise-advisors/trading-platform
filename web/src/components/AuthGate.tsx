/**
 * Keeps the dashboard from rendering to someone who is not signed in.
 *
 * This is a USABILITY gate, not a security boundary. Every API route already
 * refuses an anonymous caller with 401 and the websocket refuses the handshake;
 * this only spares the user a dashboard full of failed panels before finding
 * out they need to log in. Removing it would leak no data.
 */
import { auth, SIGN_IN_PAGE, type Me } from "@/lib/api"
import { useEffect, useState, type ReactNode } from "react"

type State =
  | { phase: "checking" }
  | { phase: "in"; user: Me }
  | { phase: "out" }
  | { phase: "error"; message: string }

export function AuthGate({ children }: { children: (user: Me) => ReactNode }) {
  const [state, setState] = useState<State>({ phase: "checking" })

  useEffect(() => {
    let alive = true
    auth
      .whoami()
      .then((user) => {
        if (!alive) return
        if (user) {
          setState({ phase: "in", user })
        } else {
          setState({ phase: "out" })
          const next = window.location.pathname + window.location.search
          window.location.assign(
            `${SIGN_IN_PAGE}?${new URLSearchParams({ reason: "required", next })}`,
          )
        }
      })
      .catch((e) => {
        // A network failure is NOT "signed out". Bouncing to the sign-in page
        // when the server is merely unreachable would strand the user in a
        // login screen that also cannot reach the server.
        if (alive) setState({ phase: "error", message: String(e?.message ?? e) })
      })
    return () => {
      alive = false
    }
  }, [])

  if (state.phase === "checking" || state.phase === "out") {
    return (
      <div className="min-h-screen grid place-items-center bg-background text-muted-foreground">
        <div className="flex items-center gap-3 text-sm">
          <span className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          {state.phase === "checking" ? "Checking your session…" : "Redirecting to sign in…"}
        </div>
      </div>
    )
  }

  if (state.phase === "error") {
    return (
      <div className="min-h-screen grid place-items-center bg-background p-6">
        <div className="max-w-md text-center space-y-3">
          <h1 className="text-lg font-semibold text-foreground">
            Cannot reach the server
          </h1>
          <p className="text-sm text-muted-foreground">{state.message}</p>
          <button
            className="text-sm text-primary underline"
            onClick={() => window.location.reload()}
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  return <>{children(state.user)}</>
}
