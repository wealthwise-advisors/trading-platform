// The Plots section of the Volume Profile study dialog: one tab per plot, each
// with Draw as / Style / Width / Colour and Show plot / Show bubble / Show title.
// Pure presentation over lib/vpPlotStyles.ts; the chart owns the state and the
// saving.

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  DRAW_AS, DRAW_AS_LABEL, LINE_STYLES, LINE_STYLE_LABEL, PLOT_LABEL, PLOT_ORDER, WIDTHS,
  type DrawAs, type LineStyle, type PlotKey, type PlotStyle, type PlotStyles,
} from "@/lib/vpPlotStyles"

const FIELD = "flex-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-foreground disabled:opacity-40"
const OPTION = "bg-[#14151c] text-[#e6edf3]"

export function VolumeProfilePlotTabs({
  styles, onChange,
}: {
  styles: PlotStyles
  onChange: (key: PlotKey, patch: Partial<PlotStyle>) => void
}) {
  return (
    <Tabs defaultValue="poc" className="gap-2">
      <TabsList aria-label="Volume Profile plots" className="w-full">
        {PLOT_ORDER.map((k) => (
          <TabsTrigger key={k} value={k} className="px-1.5 text-[11px]">{PLOT_LABEL[k]}</TabsTrigger>
        ))}
      </TabsList>

      {PLOT_ORDER.map((k) => {
        const s = styles[k]
        const id = `vp-plot-${k}`
        const isLine = s.drawAs === "line"
        return (
          <TabsContent key={k} value={k} className="space-y-2">
            <div className="flex items-center gap-2">
              <label htmlFor={`${id}-drawas`} className="w-16 text-muted-foreground">Draw as</label>
              <select id={`${id}-drawas`} value={s.drawAs} className={FIELD}
                      onChange={(e) => onChange(k, { drawAs: e.target.value as DrawAs })}>
                {DRAW_AS.map((d) => <option key={d} value={d} className={OPTION}>{DRAW_AS_LABEL[d]}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor={`${id}-style`} className="w-16 text-muted-foreground">Style</label>
              {/* Style is a line property; for markers it would do nothing, so it
                  is disabled and says why rather than silently ignored. */}
              <select id={`${id}-style`} value={s.style} className={FIELD} disabled={!isLine}
                      title={isLine ? undefined : "Style applies when drawn as a line"}
                      onChange={(e) => onChange(k, { style: e.target.value as LineStyle })}>
                {LINE_STYLES.map((st) => <option key={st} value={st} className={OPTION}>{LINE_STYLE_LABEL[st]}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor={`${id}-width`} className="w-16 text-muted-foreground">Width</label>
              <select id={`${id}-width`} value={s.width} className={FIELD}
                      onChange={(e) => onChange(k, { width: Number(e.target.value) })}>
                {WIDTHS.map((w) => <option key={w} value={w} className={OPTION}>{w}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor={`${id}-color`} className="w-16 text-muted-foreground">Colour</label>
              <input id={`${id}-color`} type="color" value={s.color}
                     onChange={(e) => onChange(k, { color: e.target.value })}
                     className="h-6 w-10 cursor-pointer rounded border border-white/10 bg-transparent" />
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
              {([
                ["show", "Show plot"],
                ["bubble", "Show bubble"],
                ["title", "Show title"],
              ] as const).map(([field, label]) => (
                <label key={field} className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={s[field]}
                         onChange={(e) => onChange(k, { [field]: e.target.checked })} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </TabsContent>
        )
      })}

      <p className="text-[11px] text-muted-foreground">
        Draw as applies to the whole-chart profile. Day and week profiles draw their
        levels as lines, using this colour, style and width.
      </p>
    </Tabs>
  )
}
