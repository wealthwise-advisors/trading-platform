/** One line when another tab or device's settings replaced this one's (lib/accountSettings.ts). */
import { useSettingsNotice } from "@/lib/accountSettings"

export function SettingsNotice() {
  const { text, set } = useSettingsNotice()
  if (!text) return null
  return (
    <div role="status" aria-live="polite"
         className="flex items-center justify-center gap-3 bg-sky-500/15 px-4 py-1.5 text-xs font-medium text-sky-800 dark:text-sky-200">
      <span>{text}</span>
      <button type="button" className="underline underline-offset-2" onClick={() => window.location.reload()}>Reload</button>
      <button type="button" aria-label="Dismiss" className="opacity-70 hover:opacity-100" onClick={() => set("")}>Dismiss</button>
    </div>
  )
}
