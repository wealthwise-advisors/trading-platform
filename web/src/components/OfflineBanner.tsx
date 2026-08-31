/**
 * Says so when the browser loses the network, and says so again when it comes back.
 *
 * WHY THIS IS NOT A LOGOUT
 * ------------------------
 * Losing the network and losing a session look identical from inside a failed
 * fetch, and treating the first as the second is the classic version of this
 * bug: it strands someone on a sign-in page that also cannot reach the server.
 * AuthGate already refuses to make that mistake; this is the other half of the
 * same rule -- tell them the connection is gone, leave the app exactly where it
 * was, and let them retry when it returns.
 *
 * `navigator.onLine` is honest about being offline and optimistic about being
 * online: it reports true for a machine on a wifi network with no route out.
 * That is why this is an ADVISORY strip rather than a gate over the app --
 * a false "online" costs nothing, and the request layer's own timeout is what
 * actually catches a dead connection.
 */
import { useEffect, useState } from "react"

export function OfflineBanner() {
  const [online, setOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine)
  // Shown briefly after recovery so the change is visible; a banner that just
  // vanishes leaves people unsure whether anything happened.
  const [justCameBack, setJustCameBack] = useState(false)

  useEffect(() => {
    function goOffline() {
      setOnline(false)
      setJustCameBack(false)
    }
    function goOnline() {
      setOnline(true)
      setJustCameBack(true)
      setTimeout(() => setJustCameBack(false), 4000)
    }
    window.addEventListener("offline", goOffline)
    window.addEventListener("online", goOnline)
    return () => {
      window.removeEventListener("offline", goOffline)
      window.removeEventListener("online", goOnline)
    }
  }, [])

  if (online && !justCameBack) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className={
        "flex items-center justify-center gap-3 px-4 py-1.5 text-xs font-medium " +
        (online
          ? "bg-emerald-500/15 text-emerald-300"
          : "bg-amber-500/15 text-amber-200")
      }
    >
      {online ? (
        <span>Back online. Anything that failed can be retried.</span>
      ) : (
        <>
          <span>
            No connection. You are still signed in — nothing has been lost, and
            requests will work again once the network returns.
          </span>
          <button
            className="underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-current"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </>
      )}
    </div>
  )
}
