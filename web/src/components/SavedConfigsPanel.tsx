import { useState } from "react"
import { useConfigStore } from "@/store/configStore"
import { listSavedConfigs, saveConfig, deleteConfig } from "@/lib/savedConfigs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"

export function SavedConfigsPanel() {
  const getSnapshot = useConfigStore((s) => s.getSnapshot)
  const loadSnapshot = useConfigStore((s) => s.loadSnapshot)

  const [name, setName] = useState("")
  const [selected, setSelected] = useState("")
  const [saved, setSaved] = useState(listSavedConfigs())
  const [justSaved, setJustSaved] = useState(false)

  function handleSave() {
    if (!name.trim()) return
    saveConfig(name.trim(), getSnapshot())
    setSaved(listSavedConfigs())
    setName("")
    setJustSaved(true)
    setTimeout(() => setJustSaved(false), 2000)
  }

  function handleLoad() {
    const entry = saved.find((c) => c.name === selected)
    if (entry) loadSnapshot(entry.config)
  }

  function handleDelete() {
    if (!selected) return
    deleteConfig(selected)
    setSaved(listSavedConfigs())
    setSelected("")
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input placeholder="Config name…" value={name} onChange={(e) => setName(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && handleSave()} />
        <Button variant="secondary" size="default" disabled={!name.trim()} onClick={handleSave}>
          💾 Save
        </Button>
      </div>
      {justSaved && <p className="text-xs text-green-400">Configuration saved.</p>}

      {saved.length > 0 && (
        <div className="flex gap-2">
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger className="w-full"><SelectValue placeholder="Load saved config…" /></SelectTrigger>
            <SelectContent>
              {saved.map((c) => <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="secondary" size="default" disabled={!selected} onClick={handleLoad}>📂</Button>
          <Button variant="secondary" size="default" disabled={!selected} onClick={handleDelete}>🗑</Button>
        </div>
      )}
    </div>
  )
}
