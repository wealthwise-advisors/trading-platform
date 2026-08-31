/**
 * Frontend crash reporting — OFF unless a DSN is configured, and off by default.
 *
 * WHY THERE IS NO SENTRY SDK HERE
 * -------------------------------
 * web/public/privacy.html §4 states, to users, that there is no error-reporting
 * service in this application. Adding one is therefore a change to a published
 * promise as well as to the code, and it must not happen as a side effect of
 * installing a dependency. So this ships as a small, inspectable reporter that
 * does nothing at all until someone sets VITE_AUTOTRADER_ERROR_DSN, and the
 * policy now describes exactly that: dormant by default, and what is sent if it
 * is ever switched on.
 *
 * It is deliberately not @sentry/react. A vendor SDK captures breadcrumbs,
 * network payloads, DOM snapshots and user identifiers by default, and every
 * one of those would need auditing against the policy above before it could be
 * turned on. What is sent from here is the whole list, visible in one function.
 *
 * WHAT IS NEVER SENT
 * ------------------
 * No cookies, no session token, no password, no request bodies, no email or
 * username, no query strings. The URL is reduced to its path for that last
 * reason: a reset link carries its token in the query.
 */

/** Vite inlines this at build time; absent in every build that does not set it. */
const DSN = import.meta.env?.VITE_AUTOTRADER_ERROR_DSN as string | undefined
const RELEASE = (import.meta.env?.VITE_AUTOTRADER_RELEASE as string | undefined) ?? "dev"

/** Dev builds report nothing: a hot-reload error is not a production signal. */
const ENABLED = Boolean(DSN) && import.meta.env?.PROD === true

export function crashReportingEnabled(): boolean {
  return ENABLED
}

/** Path only — never search or hash, which can carry reset and verify tokens. */
function safeLocation(): string {
  try {
    return window.location.pathname
  } catch {
    return "unknown"
  }
}

export interface CrashContext {
  /** Where it came from: "render", "unhandled-rejection", "window-error". */
  source: string
  /** React's component stack, when the boundary caught it. */
  componentStack?: string
}

/**
 * Report one error. Never throws, never blocks, never retries.
 *
 * A reporter that can fail loudly turns one bug into two, and one that retries
 * can turn a broken page into a burst of traffic at the moment the app is
 * least healthy.
 */
export function reportCrash(error: Error, context: CrashContext): void {
  // The console is the sink in every build that has not opted in, and is what
  // the ErrorBoundary relied on before this existed.
  console.error(`[${context.source}]`, error, context.componentStack ?? "")

  if (!ENABLED || !DSN) return

  const body = JSON.stringify({
    release: RELEASE,
    environment: "production",
    source: context.source,
    name: error.name,
    message: error.message,
    stack: error.stack?.slice(0, 8000),
    component_stack: context.componentStack?.slice(0, 4000),
    path: safeLocation(),
    user_agent: navigator.userAgent,
    at: new Date().toISOString(),
  })

  try {
    // sendBeacon survives the page being torn down, which is exactly when a
    // crash report is most likely to be lost. It also cannot be awaited, which
    // is the point: reporting must not delay showing the recovery UI.
    if (navigator.sendBeacon) {
      navigator.sendBeacon(DSN, new Blob([body], { type: "application/json" }))
      return
    }
    void fetch(DSN, {
      method: "POST",
      body,
      headers: { "Content-Type": "application/json" },
      keepalive: true,
      // No credentials: this is a third-party endpoint and the session cookie
      // has no business being attached to it.
      credentials: "omit",
    }).catch(() => { /* reporting must never surface as an error itself */ })
  } catch {
    /* nothing here is worth breaking the page for */
  }
}

/**
 * Catch the two failures a React error boundary cannot see: a rejected promise
 * nobody handled, and an error thrown outside the React tree.
 */
export function installGlobalCrashHandlers(): void {
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason
    const error = reason instanceof Error ? reason : new Error(String(reason))
    reportCrash(error, { source: "unhandled-rejection" })
  })
  window.addEventListener("error", (event) => {
    if (event.error instanceof Error) {
      reportCrash(event.error, { source: "window-error" })
    }
  })
}
