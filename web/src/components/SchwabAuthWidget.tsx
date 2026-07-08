// Port of ui/app.py's sidebar Schwab widget: status check, then the
// authorize-in-browser -> paste-redirect-URL -> submit flow. The app never
// attempts to re-authenticate on its own — a new 7-day login always needs
// the user to click through Schwab's own login page in their browser.

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { GOOD, CRITICAL } from "@/components/cards/StatCard"

export function SchwabAuthWidget() {
  const queryClient = useQueryClient()
  const [redirectUrl, setRedirectUrl] = useState("")

  const statusQ = useQuery({ queryKey: ["schwab-status"], queryFn: api.schwabStatus })
  const authUrlQ = useQuery({
    queryKey: ["schwab-auth-url"],
    queryFn: api.schwabAuthUrl,
    enabled: !!statusQ.data && statusQ.data.available && !statusQ.data.authenticated,
  })

  const submitMutation = useMutation({
    mutationFn: () => api.schwabCompleteAuth(redirectUrl),
    onSuccess: () => {
      setRedirectUrl("")
      queryClient.invalidateQueries({ queryKey: ["schwab-status"] })
    },
  })

  if (statusQ.isLoading) {
    return <p className="text-xs text-muted-foreground">Checking Schwab connection…</p>
  }
  const status = statusQ.data
  if (!status) {
    return <p className="text-xs text-destructive">Could not reach the Schwab status endpoint.</p>
  }
  if (!status.available) {
    return (
      <p className="text-xs text-destructive">
        SchwabDataProvider unavailable — {status.error ?? "check config/credentials.yaml."}
      </p>
    )
  }

  const showAuthFlow = !status.authenticated || status.needs_reauth

  return (
    <div className="space-y-2">
      {!status.authenticated && (
        <p className="text-xs" style={{ color: CRITICAL }}>Not authenticated with Schwab. Complete the steps below.</p>
      )}
      {status.authenticated && status.needs_reauth && (
        <p className="text-xs" style={{ color: "#c98500" }}>
          Schwab token expires in {status.hours_remaining.toFixed(1)} h — re-authenticate soon.
        </p>
      )}
      {status.authenticated && !status.needs_reauth && (
        <p className="text-xs" style={{ color: GOOD }}>
          Schwab connected ({status.hours_remaining.toFixed(0)} h remaining)
        </p>
      )}

      {showAuthFlow && (
        <div className="space-y-2 border border-white/6 rounded-lg p-3 bg-[#0e1424]">
          <p className="text-xs text-muted-foreground">
            <b>Step 1:</b>{" "}
            {authUrlQ.data ? (
              <a href={authUrlQ.data.auth_url} target="_blank" rel="noreferrer" className="text-primary underline">
                Click here to authorize with Schwab
              </a>
            ) : "Loading authorization link…"}
            <br />Log in, approve, then copy the full URL your browser redirects to.
          </p>
          <div className="space-y-1">
            <Label className="text-xs">Step 2: Paste redirect URL here</Label>
            <Input value={redirectUrl} onChange={(e) => setRedirectUrl(e.target.value)}
                   placeholder="https://127.0.0.1/?code=..." />
          </div>
          <Button size="sm" className="w-full" disabled={!redirectUrl || submitMutation.isPending}
                  onClick={() => submitMutation.mutate()}>
            {submitMutation.isPending ? "Submitting…" : "Submit & Save Tokens"}
          </Button>
          {submitMutation.isError && (
            <p className="text-xs text-destructive">{(submitMutation.error as Error).message}</p>
          )}
          {submitMutation.isSuccess && (
            <p className="text-xs" style={{ color: GOOD }}>Schwab authenticated successfully! Click Run Backtest.</p>
          )}
        </div>
      )}
    </div>
  )
}
