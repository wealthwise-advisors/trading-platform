// An oscillator's settings, inside the Studies panel: its inputs, its two level lines
// and its colours, all editable (user, 2026-11-27: "MFI settings ... I told you").
// The chart works the oscillator out again in the browser when a length changes
// (lib/oscCalc.ts); the Export Data workbook keeps the server's standard lengths.
import { useStudySettings } from "@/store/studySettingsStore"
import type { OscKey } from "@/lib/oscillatorStudies"
import { ColorField, FieldGroup, NumberField, ResetRow } from "./StudyFields"

export function OscillatorStudyPanel({ study }: { study: OscKey }) {
  const s = useStudySettings((st) => st.s)
  const update = useStudySettings((st) => st.update)
  const reset = useStudySettings((st) => st.reset)

  const levels = (ob: number, os: number, set: (p: { overbought?: number; oversold?: number }) => void) => (
    <FieldGroup title="Levels">
      <NumberField label="overbought" value={ob} min={1} max={100} onChange={(v) => set({ overbought: v })} />
      <NumberField label="oversold" value={os} min={0} max={99} onChange={(v) => set({ oversold: v })} />
    </FieldGroup>
  )

  if (study === "stochrsi") {
    const v = s.stochrsi
    const set = (p: Partial<typeof v>) => update("stochrsi", p)
    return (
      <div className="space-y-2">
        <FieldGroup title="Inputs">
          <NumberField label="RSI length" value={v.rsiLength} min={2} max={100} onChange={(n) => set({ rsiLength: n })} />
          <NumberField label="K period" value={v.kPeriod} min={1} max={100} onChange={(n) => set({ kPeriod: n })} />
          <NumberField label="D period" value={v.dPeriod} min={1} max={50} onChange={(n) => set({ dPeriod: n })} />
          <NumberField label="slowing period" value={v.slowing} min={1} max={50} onChange={(n) => set({ slowing: n })} />
        </FieldGroup>
        {levels(v.overbought, v.oversold, set)}
        <FieldGroup title="Colours">
          <ColorField label="FullK" value={v.kColor} onChange={(c) => set({ kColor: c })} />
          <ColorField label="FullD" value={v.dColor} onChange={(c) => set({ dColor: c })} />
        </FieldGroup>
        <ResetRow onReset={() => reset("stochrsi")} note="Wilder's RSI, simple K / D" />
      </div>
    )
  }

  const v = s[study]
  const set = (p: Partial<typeof v>) => update(study, p)
  const rsiRow = study !== "mfi"
  return (
    <div className="space-y-2">
      <FieldGroup title="Inputs">
        <NumberField label="length" value={v.length} min={rsiRow ? 2 : 1} max={200} onChange={(n) => set({ length: n })}
                     aria={`${study === "mfi" ? "MFI" : study === "rsi2" ? "RSI(2)" : "RSI(13)"} length`} />
        <div className="sf-row"><span className="sf-label">price</span>
          <span className="text-[12px]">{rsiRow ? "CLOSE · Wilder's" : "(H+L+C)/3 · needs volume"}</span></div>
      </FieldGroup>
      {levels(v.overbought, v.oversold, set)}
      <FieldGroup title="Colours">
        <ColorField label="line" value={v.color} onChange={(c) => set({ color: c })} />
        {rsiRow && (
          <>
            <ColorField label="past overbought" value={s.zones.above} onChange={(c) => update("zones", { above: c })} />
            <ColorField label="past oversold" value={s.zones.below} onChange={(c) => update("zones", { below: c })} />
          </>
        )}
      </FieldGroup>
      <ResetRow onReset={() => { reset(study); if (rsiRow) reset("zones") }} />
    </div>
  )
}
