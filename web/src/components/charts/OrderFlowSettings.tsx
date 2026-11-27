// Settings for sir's three order-flow studies, inside the Studies panel
// (user, 2026-11-27: "these three settings I am not getting").
import { useStudySettings } from "@/store/studySettingsStore"
import type { CvdStyle } from "./StudiesPanel"
import { ChoiceField, ColorField, FieldGroup, NumberField, ResetRow, ToggleField } from "./StudyFields"

export function DeltaSettings() {
  const v = useStudySettings((st) => st.s.delta)
  const update = useStudySettings((st) => st.update)
  const reset = useStudySettings((st) => st.reset)
  const set = (p: Partial<typeof v>) => update("delta", p)
  return (
    <div className="space-y-2">
      <FieldGroup title="Inputs">
        <NumberField label="strong past ±%" value={v.filter} min={1} max={100} aria="Delta filter percent"
                     onChange={(n) => set({ filter: n })} />
      </FieldGroup>
      <FieldGroup title="Colours">
        <ColorField label="buyers ahead" value={v.up} onChange={(c) => set({ up: c })} />
        <ColorField label="sellers ahead" value={v.down} onChange={(c) => set({ down: c })} />
        <ColorField label={`buyers past +${v.filter}%`} value={v.bigUp} onChange={(c) => set({ bigUp: c })} aria="strong buyers colour" />
        <ColorField label={`sellers past -${v.filter}%`} value={v.bigDown} onChange={(c) => set({ bigDown: c })} aria="strong sellers colour" />
      </FieldGroup>
      <ResetRow onReset={() => reset("delta")} note="Buyers − sellers, estimated per candle" />
    </div>
  )
}

export function CvdSettings({ style, onStyle }: { style: CvdStyle; onStyle: (s: CvdStyle) => void }) {
  const v = useStudySettings((st) => st.s.cvd)
  const update = useStudySettings((st) => st.update)
  const reset = useStudySettings((st) => st.reset)
  const set = (p: Partial<typeof v>) => update("cvd", p)
  return (
    <div className="space-y-2">
      <FieldGroup title="Display">
        <ChoiceField label="CVD shown as" value={style} options={[["bars", "Bars"], ["line", "Line"]]} onChange={onStyle} />
        <div className="sf-row"><span className="sf-label">restarts</span>
          <span className="text-[12px]">6 PM · 12 AM · 8 AM ET</span></div>
      </FieldGroup>
      <FieldGroup title="Colours">
        {style === "bars" ? (
          <>
            <ColorField label="above 0" value={v.up} onChange={(c) => set({ up: c })} />
            <ColorField label="below 0" value={v.down} onChange={(c) => set({ down: c })} />
            <ColorField label="confluence" value={v.confluence} onChange={(c) => set({ confluence: c })} />
          </>
        ) : <ColorField label="line" value={v.line} onChange={(c) => set({ line: c })} aria="CVD line colour" />}
      </FieldGroup>
      <ResetRow onReset={() => reset("cvd")} />
    </div>
  )
}

export function DivergenceSettings() {
  const v = useStudySettings((st) => st.s.div)
  const update = useStudySettings((st) => st.update)
  const reset = useStudySettings((st) => st.reset)
  const set = (p: Partial<typeof v>) => update("div", p)
  return (
    <div className="space-y-2">
      <FieldGroup title="Inputs">
        <ChoiceField label="swings" value={v.swings} options={[["10", "10 Leg"], ["3", "3 Leg"]]} onChange={(s) => set({ swings: s })} />
        <NumberField label="minimum strength" value={v.minStrength} min={0} max={20} step={0.1}
                     onChange={(n) => set({ minStrength: n })} />
        <NumberField label="strong above" value={v.strongAbove} min={0} max={50} step={0.1}
                     onChange={(n) => set({ strongAbove: n })} />
      </FieldGroup>
      <FieldGroup title="Kinds">
        <ToggleField label="Regular" checked={v.regular} onChange={(on) => set({ regular: on })} aria="Show Regular divergences" />
        <ToggleField label="Hidden" checked={v.hidden} onChange={(on) => set({ hidden: on })} aria="Show Hidden divergences" />
      </FieldGroup>
      <FieldGroup title="Colours">
        <ColorField label="bullish" value={v.bull} onChange={(c) => set({ bull: c })} />
        <ColorField label="bearish" value={v.bear} onChange={(c) => set({ bear: c })} />
      </FieldGroup>
      <ResetRow onReset={() => reset("div")} note="Strength = |ΔCVD| ÷ VolumeAvg" />
    </div>
  )
}
