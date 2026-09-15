import { describe, expect, it } from "vitest"
import {
  MAX_LEVEL_MARKERS, PLOT_ORDER, bubbleAnnotation, defaultPlotStyles, levelTrace,
  lineWidthPx, normalizePlotStyles, plotToggles, titleEntries,
} from "./vpPlotStyles"

type AnyTrace = {
  mode: string; x: string[]; y: number[]; name: string
  line?: { color: string; width: number; dash: string }
  marker?: { symbol: string; size: number; color: string }
}

describe("defaults are the chart as it was drawn before this change", () => {
  const d = defaultPlotStyles()

  it("POC solid sky, value area dashed light sky, profile edges dotted slate", () => {
    expect([d.poc.style, d.poc.color]).toEqual(["solid", "#38bdf8"])
    expect([d.vah.style, d.vah.color, d.val.style, d.val.color]).toEqual(["dash", "#7dd3fc", "dash", "#7dd3fc"])
    expect([d.profileHigh.style, d.profileHigh.color, d.profileLow.style, d.profileLow.color])
      .toEqual(["dot", "#94a3b8", "dot", "#94a3b8"])
  })

  it("same visibility: POC and the value area on, profile edges off", () => {
    expect(plotToggles(d)).toEqual({ poc: true, vah: true, val: true, profileHigh: false, profileLow: false })
  })

  it("lines, width 1 drawn at the previous 1.2px, no bubbles, no titles", () => {
    for (const k of PLOT_ORDER) {
      expect(d[k].drawAs).toBe("line")
      expect(lineWidthPx(d[k].width)).toBe(1.2)
      expect(d[k].bubble).toBe(false)
      expect(d[k].title).toBe(false)
    }
  })

  it("hands out copies, so a caller cannot change the defaults", () => {
    const a = defaultPlotStyles()
    a.poc.color = "#000000"
    expect(defaultPlotStyles().poc.color).toBe("#38bdf8")
  })
})

describe("normalizePlotStyles", () => {
  it("carries an older saved default's show flags across", () => {
    const s = normalizePlotStyles(undefined, { poc: false, profileHigh: true })
    expect(s.poc.show).toBe(false)
    expect(s.profileHigh.show).toBe(true)
    expect(s.vah.show).toBe(true)
  })

  it("a plots entry wins over the legacy flag", () => {
    const s = normalizePlotStyles({ poc: { show: true } }, { poc: false })
    expect(s.poc.show).toBe(true)
  })

  it("keeps valid fields and replaces invalid ones individually", () => {
    const s = normalizePlotStyles({
      vah: { drawAs: "squares", style: "zigzag", width: 9, color: "#ABCDEF", bubble: true, title: "yes" },
    })
    expect(s.vah.drawAs).toBe("squares")
    expect(s.vah.style).toBe("dash")
    expect(s.vah.width).toBe(1)
    expect(s.vah.color).toBe("#abcdef")
    expect(s.vah.bubble).toBe(true)
    expect(s.vah.title).toBe(false)
  })

  it("rejects colours that are not six-digit hex", () => {
    for (const color of ["red", "#fff", "rgb(1,2,3)", "#12345g"]) {
      expect(normalizePlotStyles({ poc: { color } }).poc.color).toBe("#38bdf8")
    }
  })

  it("survives garbage", () => {
    expect(normalizePlotStyles("nope", 7)).toEqual(defaultPlotStyles())
    expect(normalizePlotStyles([1, 2], [])).toEqual(defaultPlotStyles())
  })
})

describe("levelTrace", () => {
  const xs = Array.from({ length: 1000 }, (_, i) => `2026-01-01T00:${String(i).padStart(4, "0")}`)

  it("Line: a full-width line with the plot's colour, dash and width", () => {
    const t = levelTrace("POC", 101.5, xs, { ...defaultPlotStyles().poc, style: "longdash", width: 3, color: "#123456" }) as unknown as AnyTrace
    expect(t.mode).toBe("lines")
    expect(t.x.length).toBe(1000)
    expect(new Set(t.y)).toEqual(new Set([101.5]))
    expect(t.line).toEqual({ color: "#123456", width: 3, dash: "longdash" })
  })

  it("Points / Squares / Triangles: sampled markers of the right shape", () => {
    for (const [drawAs, symbol] of [["points", "circle"], ["squares", "square"], ["triangles", "triangle-up"]] as const) {
      const t = levelTrace("VAHigh", 99, xs, { ...defaultPlotStyles().vah, drawAs, width: 2 }) as unknown as AnyTrace
      expect(t.mode).toBe("markers")
      expect(t.marker?.symbol).toBe(symbol)
      expect(t.marker?.size).toBe(7)
      expect(t.x.length).toBeLessThanOrEqual(MAX_LEVEL_MARKERS + 1)
    }
  })

  it("keeps the value in the tooltip", () => {
    const t = levelTrace("VALow", 98, xs, defaultPlotStyles().val) as unknown as { hovertemplate: string }
    expect(t.hovertemplate).toContain("VALow")
  })
})

describe("bubbleAnnotation", () => {
  const style = { ...defaultPlotStyles().poc, color: "#ff8800" }

  it("sits outside the plot on the price axis side, filled with the plot colour", () => {
    const left = bubbleAnnotation(100.125, style, "left")
    expect([left.x, left.xanchor, left.y, left.text, left.bgcolor]).toEqual([0, "right", 100.125, "100.13", "#ff8800"])
    const right = bubbleAnnotation(100, style, "right")
    expect([right.x, right.xanchor]).toEqual([1, "left"])
  })
})

describe("titleEntries", () => {
  const values = { poc: 100, profileHigh: 105, profileLow: 95, vah: 102.5, val: null }

  it("only shown, titled plots with a value, in tab order", () => {
    const s = defaultPlotStyles()
    s.poc.title = true
    s.vah.title = true
    s.val.title = true          // no value -> left out
    s.profileHigh.title = true  // hidden -> left out
    expect(titleEntries(s, values)).toBe("POC: 100.00  ·  VAHigh: 102.50")
  })

  it("empty when no plot asks for a title", () => {
    expect(titleEntries(defaultPlotStyles(), values)).toBe("")
  })
})
