/**
 * The pieces the backtest config panel is built from.
 *
 * Pulled out of ConfigForm because that file was one 335-line return statement in
 * which every section styled itself, so "make the headings consistent" meant
 * editing eight places and hoping. A section is now a component, and a heading
 * cannot drift from its neighbours.
 *
 * The visual grammar, which is the point of the redesign:
 *
 *   * every section opens with an icon and a coloured uppercase label, so the
 *     panel can be scanned by colour before it is read
 *   * every choice in a dropdown carries an icon and a line saying what it does,
 *     rather than a bare name the reader has to already understand
 *   * every slider shows its value in a box beside it, not as text underneath --
 *     a number you can read at a glance while dragging
 */

import type { CSSProperties, ReactNode } from "react"
import { Slider } from "@/components/ui/slider"
import {
  Database, CandlestickChart, Clock, Target, SlidersHorizontal, ShieldCheck,
  CalendarRange, Sunrise, Activity, Info,
} from "lucide-react"

/**
 * The accent a section is drawn in, so the panel can be scanned by colour
 * before it is read.
 *
 * These are named for the HUE, not for what the section is about. The previous
 * set was named by topic -- and had rotted into `amber: "text-[#3b82f6]"` and
 * `cyan: "text-[#3b82f6]"`, two keys promising colours the file did not draw.
 * A name that lies about its own value is worse than no name: it is the one
 * thing a reader will not think to check.
 *
 * The palette is a dark trading terminal's, as requested on 2026-09-15: cool
 * blue as the main accent, and teal, green, orange and a single small purple
 * only where they separate one kind of setting from another. No yellow or
 * gold. The colour marks the heading and its icon; the controls beneath stay
 * neutral grey, apart from a slider's filled track and thumb. Each value is a
 * 400-weight tint, bright enough for small bold uppercase text on the panel.
 */
export type Accent =
  "blue" | "sky" | "teal" | "steel" | "green" | "orange" | "ember" | "violet"

// Each hue is a TOKEN now, not a literal. The values these replace were tuned
// against a dark sidebar and came out at 1.8:1 to 2.6:1 on a light one; the
// tokens hold the same hue at a lightness that works in whichever theme is
// on. See the note beside --sec-* in index.css.
const ACCENT: Record<Accent, { text: string; hex: string }> = {
  blue:   { text: "text-[color:var(--sec-blue)]",   hex: "var(--sec-blue)" },    // structure: Timeframe Selector, Capital & Risk
  sky:    { text: "text-[color:var(--sec-sky)]",    hex: "var(--sec-sky)" },     // where the data comes from
  teal:   { text: "text-[color:var(--sec-teal)]",   hex: "var(--sec-teal)" },    // what and when: Symbol, Date Range
  steel:  { text: "text-[color:var(--sec-steel)]",  hex: "var(--sec-steel)" },   // Interval Picker -- muted, so it reads apart from the Selector
  green:  { text: "text-[color:var(--sec-green)]",  hex: "var(--sec-green)" },   // Strategy
  orange: { text: "text-[color:var(--sec-orange)]", hex: "var(--sec-orange)" },  // the numbers you tune
  ember:  { text: "text-[color:var(--sec-ember)]",  hex: "var(--sec-ember)" },   // Session Hours -- orange, restrained
  violet: { text: "text-[color:var(--sec-violet)]", hex: "var(--sec-violet)" },  // ZigZag Swings -- the one purple, kept small
}

export const SECTION_ICON = {
  source: Database,
  symbol: CandlestickChart,
  timeframe: Clock,
  strategy: Target,
  params: SlidersHorizontal,
  capital: ShieldCheck,
  dates: CalendarRange,
  session: Sunrise,
  zigzag: Activity,
} as const

interface SectionProps {
  icon: keyof typeof SECTION_ICON
  label: string
  accent?: Accent
  children: ReactNode
  /** Extra note shown to the right of the heading. */
  aside?: ReactNode
  /** Position in the panel, shown before the name.
   *
   *  The panel is a form you work down in order -- pick a source, then a
   *  symbol, then a timeframe, and so on -- and the number says so. It also
   *  gives a way to refer to a section out loud ("section 7") that a colour
   *  and an icon do not. Passed in rather than counted automatically because
   *  the sections are written out one by one, not mapped over a list. */
  step?: number
  /** Scroll target for the icon rail in App.tsx. */
  anchor?: string
}

/**
 * One labelled group. The heading is the only place a section name is styled, so
 * they cannot diverge.
 */
export function Section({ icon, label, accent = "blue", children, aside, step, anchor }: SectionProps) {
  const Icon = SECTION_ICON[icon]
  const { text, hex } = ACCENT[accent]
  return (
    // --slider-accent: a slider in this section fills in the section's colour
    // unless the field sets its own (see .cfg-scope in index.css).
    <section className="space-y-2.5" data-cfg-section={anchor}
             style={{ "--slider-accent": hex } as CSSProperties}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${text}`} aria-hidden />
          <h3 className={`text-[11px] font-bold uppercase tracking-[0.14em] ${text}`}>
            {step != null && <span className="opacity-70">{step}. </span>}
            {label}
          </h3>
        </div>
        {aside}
      </div>
      {children}
    </section>
  )
}

/** A bordered group, for sections holding several related fields. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-[color:var(--hairline-mid)] bg-[color:var(--raise-1)] p-3.5 space-y-3.5 ${className}`}>
      {children}
    </div>
  )
}

/**
 * A choice in a dropdown: icon, name, and a line saying what picking it does.
 *
 * The descriptions matter more than they look. "Synthetic Data" and "My Historical
 * Data (CSV)" are not self-explanatory to someone opening this for the first time,
 * and the difference between them decides whether the result means anything.
 */
export function Choice({
  icon, title, description,
}: { icon: ReactNode; title: string; description?: string }) {
  return (
    <span className="flex items-center gap-2.5 py-0.5">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg
                       border border-[color:var(--hairline-mid)] bg-[color:var(--raise-2)]">
        {icon}
      </span>
      <span className="flex flex-col leading-tight">
        <span className="font-medium">{title}</span>
        {description && (
          <span className="text-[11px] text-muted-foreground">{description}</span>
        )}
      </span>
    </span>
  )
}

/**
 * A field with an icon and its control on the right.
 *
 * Used for Capital & Risk, where three numbers sit together and the icon is what
 * tells them apart at a glance.
 */
export function FieldRow({
  icon, label, hint, children,
}: { icon: ReactNode; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-2.5 min-w-0">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg
                         border border-[color:var(--hairline-mid)] bg-[color:var(--raise-2)]">
          {icon}
        </span>
        <span className="flex flex-col leading-tight min-w-0">
          <span className="text-[13px] leading-snug">{label}</span>
          {hint && <span className="text-[11px] text-muted-foreground truncate">{hint}</span>}
        </span>
      </span>
      <div className="w-[122px] shrink-0">{children}</div>
    </div>
  )
}

/**
 * A slider with its value in a box beside it.
 *
 * The value used to sit as text under the label, which is the wrong place: while
 * dragging, the eye is on the thumb, and the number has to be next to it to be
 * read. The box is also editable, so a precise value does not require nudging a
 * slider pixel by pixel.
 */
export function SliderField({
  label, help, value, onChange, min, max, step, dot, color, format,
}: {
  label: string
  help?: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  step: number
  /** A coloured dot before the label, marking which series the field sets. */
  dot?: string
  /** The slider's filled track and thumb. Omitted, the section's colour. */
  color?: string
  format?: (v: number) => string
}) {
  return (
    <div className="space-y-1.5"
         style={color ? ({ "--slider-accent": color } as CSSProperties) : undefined}>
      <div className="flex items-center justify-between gap-3">
        <label className="flex items-center gap-1.5 text-sm">
          {dot && (
            <span className="h-2 w-2 rounded-full shrink-0" style={{ background: dot }} aria-hidden />
          )}
          {label}
          {help && (
            // aria-label on a bare span names an element with no role to carry a
            // name -- ARIA prohibits it, and axe flagged all five of these. The
            // text now lives in the DOM instead: visible to a screen reader,
            // shown on hover by the title, and hidden from sight.
            <span title={help} className="cursor-help text-muted-foreground">
              <Info className="h-3.5 w-3.5" aria-hidden />
              <span className="sr-only">{help}</span>
            </span>
          )}
        </label>
        <input
          type="number"
          value={value}
          min={min} max={max} step={step}
          onChange={(e) => {
            const v = Number(e.target.value)
            // A half-typed field yields NaN; keep the last good value rather than
            // sending NaN through to the request.
            if (Number.isFinite(v)) onChange(v)
          }}
          className="w-[86px] shrink-0 rounded-lg border border-[color:var(--hairline-mid)] bg-[color:var(--raise-1)]
                     px-3 py-2 text-center text-sm tabular-nums
                     focus:border-[color:var(--hairline-focus)] focus:outline-none focus:ring-2 focus:ring-blue-400/25"
          aria-label={label}
        />
      </div>
      <Slider
        min={min} max={max} step={step}
        value={[value]}
        onValueChange={([v]) => onChange(v)}
        aria-label={label}
      />
      {format && (
        <p className="text-[11px] text-muted-foreground">{format(value)}</p>
      )}
    </div>
  )
}

/**
 * A toggle switch, as the references show, rather than a native checkbox.
 *
 * Built from a button and two divs -- the project has Radix for menus and selects
 * but no switch primitive, and one control is not worth a dependency. The button
 * carries role="switch" and aria-checked, so it is announced correctly and driven
 * by Space/Enter exactly as a checkbox would be.
 */
export function ToggleSwitch({
  checked, onChange, label, hint, disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: ReactNode
  hint?: ReactNode
  disabled?: boolean
}) {
  return (
    <label className="flex items-center justify-between gap-3 cursor-pointer">
      <span className="min-w-0 text-xs">
        {label}
        {hint && <span className="text-muted-foreground"> {hint}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/50
                    disabled:opacity-50 ${checked ? "bg-[#2563eb]" : "bg-[color:var(--raise-5)]"}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform
                      ${checked ? "translate-x-[22px]" : "translate-x-0.5"}`}
        />
      </button>
    </label>
  )
}

/**
 * Date-range shortcuts. Each writes the SAME two fields the pickers write, so
 * nothing new is stored and the pickers remain the source of truth.
 */
export function QuickPresets({
  onPick,
}: { onPick: (days: number) => void }) {
  const PRESETS: ReadonlyArray<readonly [string, number]> = [
    ["1D", 1], ["5D", 5], ["1M", 30], ["3M", 90], ["6M", 180],
  ]
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] text-muted-foreground mr-0.5">Quick in</span>
      {PRESETS.map(([label, days]) => (
        <button
          key={label}
          type="button"
          onClick={() => onPick(days)}
          className="rounded-lg border border-[color:var(--hairline-mid)] bg-[color:var(--raise-1)] px-2 py-1
                     text-[11px] font-medium text-muted-foreground transition-colors
                     hover:border-teal-400/40 hover:bg-teal-400/10 hover:text-teal-200"
        >
          {label}
        </button>
      ))}
    </div>
  )
}
