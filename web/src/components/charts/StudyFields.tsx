// The controls a study's settings are built from, inside the Studies panel
// (2026-11-27): a numbered field, a colour, an on/off, a choice, grouped under
// small headings -- Inputs, Levels, Colours -- so each study opens step by step.
import { useEffect, useState, type ReactNode } from "react"
import { RotateCcw } from "lucide-react"
import { InfoDot } from "@/components/ui/info-dot"

/** The field's name, and its ⓘ when it has an explanation. */
function Name({ label, help }: { label: string; help?: string }) {
  return (
    <span className="sf-label flex items-center gap-1.5">
      {label}
      {help && <InfoDot label={label} align="left"><span className="text-[12px] leading-snug">{help}</span></InfoDot>}
    </span>
  )
}

export function FieldGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="sf-group">
      <legend className="sf-legend">{title}</legend>
      <div className="space-y-1.5">{children}</div>
    </fieldset>
  )
}

/** A number, kept in range. An emptied box stays empty while typing. */
export function NumberField({ label, value, onChange, min, max, step = 1, aria, help }: {
  label: string; value: number; onChange: (n: number) => void
  min: number; max: number; step?: number; aria?: string; help?: string
}) {
  const [draft, setDraft] = useState(String(value))
  useEffect(() => { setDraft(String(value)) }, [value])
  return (
    <div className="sf-row">
      <Name label={label} help={help} />
      <input type="number" className="sf-input" min={min} max={max} step={step} value={draft}
             aria-label={aria ?? label}
             onChange={(e) => {
               setDraft(e.target.value)
               const n = e.target.valueAsNumber
               if (Number.isFinite(n)) onChange(Math.min(max, Math.max(min, n)))
             }}
             onBlur={() => setDraft(String(value))} />
    </div>
  )
}

export function ColorField({ label, value, onChange, aria, help }: {
  label: string; value: string; onChange: (c: string) => void; aria?: string; help?: string
}) {
  return (
    <div className="sf-row">
      <Name label={label} help={help} />
      <span className="flex items-center gap-2">
        <span className="font-mono text-[11px] text-muted-foreground">{value.toUpperCase()}</span>
        <input type="color" className="sf-color" value={value} aria-label={aria ?? `${label} colour`}
               onChange={(e) => onChange(e.target.value)} />
      </span>
    </div>
  )
}

export function ToggleField({ label, checked, onChange, aria, help }: {
  label: string; checked: boolean; onChange: (on: boolean) => void; aria?: string; help?: string
}) {
  return (
    <div className="sf-row">
      <Name label={label} help={help} />
      <input type="checkbox" className="study-switch" checked={checked} aria-label={aria ?? label}
             onChange={(e) => onChange(e.target.checked)} />
    </div>
  )
}

export function ChoiceField<T extends string>({ label, value, options, onChange, help }: {
  label: string; value: T; options: [T, string][]; onChange: (v: T) => void; help?: string
}) {
  return (
    <div className="sf-row">
      <Name label={label} help={help} />
      <span className="sf-seg" role="radiogroup" aria-label={label}>
        {options.map(([v, text]) => (
          <button key={v} type="button" role="radio" aria-checked={value === v}
                  className={value === v ? "sf-seg-on" : undefined} onClick={() => onChange(v)}>{text}</button>
        ))}
      </span>
    </div>
  )
}

export function ResetRow({ onReset, note }: { onReset: () => void; note?: string }) {
  return (
    <div className="flex items-center justify-between gap-2 pt-1">
      <span className="text-[11px] text-muted-foreground">{note}</span>
      <button type="button" className="ui-link-btn gap-1" onClick={onReset}>
        <RotateCcw className="h-3 w-3" aria-hidden /> Reset
      </button>
    </div>
  )
}

/** A line's width and dash, for an oscillator's plot. */
export function LineFields({ width, dash, onChange }: {
  width: number; dash: "solid" | "dash" | "dot"
  onChange: (p: { width?: number; dash?: "solid" | "dash" | "dot" }) => void
}) {
  return (
    <>
      <ChoiceField label="width" value={String(width)}
                   options={[...new Set([1, 1.5, 2, 3, width])].sort((x, y) => x - y).map((w) => [String(w), String(w)] as [string, string])}
                   onChange={(w) => onChange({ width: Number(w) })} help="How thick the line is drawn, in pixels." />
      <ChoiceField label="style" value={dash} options={[["solid", "Solid"], ["dash", "Dashed"], ["dot", "Dotted"]]}
                   onChange={(d) => onChange({ dash: d })} />
    </>
  )
}
