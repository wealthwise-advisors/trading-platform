// Settings for Swing count and Economic events, inside the Studies panel (2026-11-27).
// The swing deviations are the same three values as the sidebar's ZigZag Swings
// section -- one setting, two places to reach it -- and apply on the next run,
// because the swings are worked out by the backtest.
import { useConfigStore, ZIGZAG_DEV_MAX, ZIGZAG_DEV_STEP } from "@/store/configStore"
import { useStudySettings } from "@/store/studySettingsStore"
import { ChoiceField, FieldGroup, NumberField, ResetRow } from "./StudyFields"

export function SwingCountSettings() {
  const cfg = useConfigStore()
  return (
    <div className="space-y-2">
      <FieldGroup title="Deviation %">
        <NumberField label="10 Leg (Swing A, B, C)" value={cfg.zigzagDev10} min={ZIGZAG_DEV_STEP} max={ZIGZAG_DEV_MAX}
                     step={ZIGZAG_DEV_STEP} aria="10 Leg deviation" onChange={(v) => cfg.setField("zigzagDev10", v)} />
        <NumberField label="3 Leg (1, 2, 3)" value={cfg.zigzagDev3} min={ZIGZAG_DEV_STEP} max={ZIGZAG_DEV_MAX}
                     step={ZIGZAG_DEV_STEP} aria="3 Leg deviation" onChange={(v) => cfg.setField("zigzagDev3", v)} />
        <NumberField label="1 Leg (i, ii, iii)" value={cfg.zigzagDev1} min={0} max={ZIGZAG_DEV_MAX}
                     step={ZIGZAG_DEV_STEP} aria="1 Leg deviation" onChange={(v) => cfg.setField("zigzagDev1", v)} />
      </FieldGroup>
      <p className="text-[11px] text-muted-foreground">Applies on the next Run Backtest. Same values as the sidebar's ZigZag Swings.</p>
    </div>
  )
}

export function EventsSettings() {
  const v = useStudySettings((st) => st.s.events)
  const update = useStudySettings((st) => st.update)
  const reset = useStudySettings((st) => st.reset)
  return (
    <div className="space-y-2">
      <FieldGroup title="Show">
        <ChoiceField label="impact" value={v.medium ? "both" : "high"}
                     options={[["high", "High only"], ["both", "High + Medium"]]}
                     onChange={(c) => update("events", { medium: c === "both" })} />
      </FieldGroup>
      <ResetRow onReset={() => reset("events")} note="Amber = high, sky = medium" />
    </div>
  )
}
