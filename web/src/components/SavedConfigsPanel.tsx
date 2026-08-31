import { useCallback, useEffect, useState } from "react"
import { useConfigStore } from "@/store/configStore"
import {
  listSavedConfigs, saveConfig, deleteConfig, migrateLegacyConfigs,
  type SavedConfig,
} from "@/lib/savedConfigs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { Save, FolderOpen, Trash2 } from "lucide-react"

/**
 * Configs now live on the account rather than in this browser, so every action
 * here is a request that can be slow, fail, or be double-clicked.
 *
 * `busy` is one flag rather than three because the three actions share one
 * list: allowing a delete to start while a save is in flight would leave the
 * panel showing whichever response landed second.
 */
type Busy = null | "loading" | "saving" | "deleting"

export function SavedConfigsPanel() {
  const getSnapshot = useConfigStore((s) => s.getSnapshot)
  const loadSnapshot = useConfigStore((s) => s.loadSnapshot)

  const [name, setName] = useState("")
  const [selected, setSelected] = useState("")
  const [saved, setSaved] = useState<SavedConfig[]>([])
  const [busy, setBusy] = useState<Busy>("loading")
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  //: Armed by the first press of Delete, spent by the second.
  const [confirming, setConfirming] = useState(false)

  const refresh = useCallback(async () => {
    const rows = await listSavedConfigs()
    setSaved(rows)
    return rows
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        // Anything still in localStorage from before these were server-side
        // goes up first, so the list below is the whole picture.
        const moved = await migrateLegacyConfigs()
        const rows = await refresh()
        if (!alive) return
        if (moved > 0) {
          setNotice(`Moved ${moved} saved configuration${moved === 1 ? "" : "s"} to your account.`)
        }
        setSaved(rows)
      } catch (e) {
        if (alive) setError((e as Error)?.message ?? "Could not load your saved configurations.")
      } finally {
        if (alive) setBusy(null)
      }
    })()
    return () => { alive = false }
  }, [refresh])

  async function handleSave() {
    // Guarded as well as disabled: a keyboard repeat on Enter can fire twice
    // before React re-renders the disabled button.
    if (busy || !name.trim()) return
    setBusy("saving")
    setError("")
    try {
      await saveConfig(name.trim(), getSnapshot())
      await refresh()
      setName("")
      setNotice("Configuration saved.")
      setTimeout(() => setNotice(""), 2000)
    } catch (e) {
      setError((e as Error)?.message ?? "Could not save that configuration.")
    } finally {
      setBusy(null)
    }
  }

  function handleLoad() {
    const entry = saved.find((c) => c.name === selected)
    if (entry) loadSnapshot(entry.config)
  }

  async function handleDelete() {
    if (busy || !selected) return
    // Two presses, not one. This used to delete on a single click of an
    // icon-only button sitting next to Load -- and now that configs live on the
    // account rather than in this browser, the click destroys something that
    // followed the person between devices and cannot be recovered. The button
    // says what it will do before it does it.
    if (!confirming) {
      setConfirming(true)
      return
    }
    setConfirming(false)
    setBusy("deleting")
    setError("")
    try {
      await deleteConfig(selected)
      await refresh()
      setSelected("")
    } catch (e) {
      setError((e as Error)?.message ?? "Could not delete that configuration.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          placeholder="Config name…"
          value={name}
          disabled={busy === "loading"}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          aria-label="Name for this configuration"
        />
        <Button
          variant="secondary"
          size="default"
          disabled={!name.trim() || busy !== null}
          onClick={handleSave}
        >
          <Save className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {busy === "saving" ? "Saving…" : "Save"}
        </Button>
      </div>

      {notice && <p role="status" aria-live="polite" className="text-xs text-green-400">{notice}</p>}
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}

      {busy === "loading" ? (
        <p className="text-xs text-muted-foreground">Loading your saved configurations…</p>
      ) : saved.length === 0 ? (
        // A deliberate empty state rather than nothing at all: the panel used
        // to render as a lone text box, which reads as a feature that is
        // broken rather than one not used yet.
        !error && (
          <p className="text-xs text-muted-foreground">
            No saved configurations yet. Set up the panel above the way you like
            it, give it a name, and press Save — it will be here on any device
            you sign in from.
          </p>
        )
      ) : (
        <div className="flex gap-2">
          <Select value={selected}
                  onValueChange={(v) => { setSelected(v); setConfirming(false) }}>
            <SelectTrigger className="w-full" aria-label="Saved configurations">
              <SelectValue placeholder="Load saved config…" />
            </SelectTrigger>
            <SelectContent>
              {saved.map((c) => <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="secondary" size="default" disabled={!selected || busy !== null}
                  onClick={handleLoad} aria-label="Load">
            <FolderOpen className="h-3.5 w-3.5 shrink-0" />
          </Button>
          <Button
            variant={confirming ? "destructive" : "secondary"}
            size="default"
            disabled={!selected || busy !== null}
            onClick={handleDelete}
            onBlur={() => setConfirming(false)}
            aria-label={confirming
              ? `Confirm deleting ${selected}` : `Delete ${selected || "configuration"}`}
            title={confirming ? "Press again to delete permanently" : "Delete"}
          >
            <Trash2 className="h-3.5 w-3.5 shrink-0" />
            {confirming && <span className="ml-1 text-xs">Sure?</span>}
          </Button>
        </div>
      )}
    </div>
  )
}
