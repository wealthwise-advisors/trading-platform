/**
 * The last thing between a thrown render and a white page.
 *
 * React's default behaviour when a component throws during render is to
 * unmount the whole tree. There is no message, no recovery, and nothing in the
 * page to say what happened -- the tab simply goes blank. On a deployed app
 * that is indistinguishable from "the site is down", and because nothing is
 * reported anywhere, the operator's first notice of it is somebody saying so.
 *
 * This does not replace the existing error handling and must not be confused
 * with it. lib/api.ts already turns a FAILED REQUEST into a message a panel can
 * render; that path is untouched. This catches the other kind -- a defect in
 * rendering, a malformed frame from the replay socket, a chart handed a shape
 * it did not expect -- which no try/catch around a fetch can see.
 */
import { Component, type ErrorInfo, type ReactNode } from "react"
import { reportCrash } from "@/lib/crashReporter"

interface Props {
  children: ReactNode
  /** Shown above the message, so a boundary around one panel can say which. */
  label?: string
}

interface State {
  error: Error | null
  /** React's own component stack. Kept for the log, never rendered. */
  info: ErrorInfo | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, info: null }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ info })
    // Goes to the console in every build, and onward to a reporting endpoint
    // ONLY when one has been configured -- see lib/crashReporter.ts, and §4 of
    // web/public/privacy.html, which describes exactly that arrangement.
    reportCrash(error, {
      source: "render",
      componentStack: info?.componentStack ?? undefined,
    })
  }

  private reset = () => this.setState({ error: null, info: null })

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div
        role="alert"
        className="min-h-screen grid place-items-center bg-background p-6 text-foreground"
      >
        <div className="max-w-md space-y-4 text-center">
          <h1 className="text-lg font-semibold">
            {this.props.label ?? "Something went wrong on this page"}
          </h1>
          <p className="text-sm text-muted-foreground">
            The page hit an unexpected error and stopped rendering. Your account
            and your saved backtests are not affected.
          </p>
          {/*
            The message, not the stack. A stack trace names internal paths and
            module structure to anyone who can see the screen, and it is not
            something a user can act on. It is in the browser console for
            whoever is debugging, which is where it belongs.
          */}
          <p className="text-xs font-mono text-muted-foreground/80 break-words">
            {error.message || error.name}
          </p>
          <div className="flex items-center justify-center gap-2">
            <button
              className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              onClick={this.reset}
            >
              Try again
            </button>
            <button
              className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              onClick={() => window.location.reload()}
            >
              Reload the page
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            Try again re-renders without reloading, which recovers a one-off
            failure and keeps what is already loaded. Reload starts clean.
          </p>
        </div>
      </div>
    )
  }
}
