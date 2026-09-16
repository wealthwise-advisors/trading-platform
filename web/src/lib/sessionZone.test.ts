// The Session Hours zone is a LABEL, not a filter. Every test here exists to
// hold that line: whatever zone is showing, the pair handed to the backend is
// the same Eastern pair it always was. A conversion that leaked into what is
// stored would change which bars a backtest runs on -- and it would look like a
// strategy result, not a timezone bug.

import { describe, it, expect } from "vitest"
import {
  SESSION_ZONES, ZONE_KEY, fromZone, loadZoneOffset, saveZoneOffset,
  shiftClock, toZone, zoneShort,
} from "./sessionZone"

function memStore(seed: Record<string, string> = {}) {
  const data = { ...seed }
  return {
    data,
    getItem: (k: string) => (k in data ? data[k] : null),
    setItem: (k: string, v: string) => { data[k] = v },
  }
}

const throwing = {
  getItem: () => { throw new Error("blocked") },
  setItem: () => { throw new Error("blocked") },
}

describe("the four zones", () => {
  it("are Eastern, Central, Mountain and Pacific, an hour apart", () => {
    expect(SESSION_ZONES.map((z) => z.short)).toEqual(["ET", "CT", "MT", "PT"])
    expect(SESSION_ZONES.map((z) => z.offset)).toEqual([0, -60, -120, -180])
  })

  it("name the Eastern one as the exchange clock, since that is what is stored", () => {
    expect(SESSION_ZONES[0].label).toMatch(/exchange/i)
  })

  it("zoneShort falls back to ET for an offset no zone uses", () => {
    expect(zoneShort(-60)).toBe("CT")
    expect(zoneShort(-999)).toBe("ET")
  })
})

describe("the RTH window in each zone", () => {
  it.each([
    [0, "09:30", "16:00"],
    [-60, "08:30", "15:00"],
    [-120, "07:30", "14:00"],
    [-180, "06:30", "13:00"],
  ])("offset %i shows 09:30-16:00 ET as %s-%s", (off, from, to) => {
    expect(toZone("09:30", off)).toBe(from)
    expect(toZone("16:00", off)).toBe(to)
  })
})

describe("wrapping past midnight", () => {
  // The Globex preset is 18:00-17:00 ET. On Pacific that is 15:00-14:00, and
  // an early-morning Eastern time goes backwards over midnight.
  it("the Globex open moves back within the same day", () => {
    expect(toZone("18:00", -180)).toBe("15:00")
    expect(toZone("17:00", -180)).toBe("14:00")
  })

  it("00:30 ET is 21:30 the previous evening on Pacific", () => {
    expect(toZone("00:30", -180)).toBe("21:30")
  })

  it("and typing 22:00 PT stores 01:00 ET, wrapping forward", () => {
    expect(fromZone("22:00", -180)).toBe("01:00")
  })
})

describe("round trip", () => {
  it("every zone returns the exact Eastern time it was given", () => {
    for (const z of SESSION_ZONES) {
      for (const t of ["00:00", "00:30", "09:30", "12:00", "16:00", "17:59", "18:00", "23:59"]) {
        expect(fromZone(toZone(t, z.offset), z.offset)).toBe(t)
      }
    }
  })

  it("Eastern is the identity, so nothing shifts when no zone is chosen", () => {
    for (const t of ["09:30", "16:00", "18:00"]) {
      expect(toZone(t, 0)).toBe(t)
      expect(fromZone(t, 0)).toBe(t)
    }
  })
})

describe("input that is not a time", () => {
  // A field mid-edit must not be rewritten under the cursor.
  it.each(["", "   ", "9:3", "nope", "24:00", "12:60", "12-30"])(
    "%s is returned untouched", (bad) => {
      expect(shiftClock(bad, -60)).toBe(bad)
    })

  it("accepts a single-digit hour", () => {
    expect(shiftClock("9:30", -60)).toBe("08:30")
  })
})

describe("the choice persists per browser", () => {
  it("round-trips through storage", () => {
    const s = memStore()
    saveZoneOffset(-120, s)
    expect(s.data[ZONE_KEY]).toBe("-120")
    expect(loadZoneOffset(s)).toBe(-120)
  })

  it("falls back to Eastern for an empty, corrupt or unknown value", () => {
    expect(loadZoneOffset(memStore())).toBe(0)
    expect(loadZoneOffset(memStore({ [ZONE_KEY]: "banana" }))).toBe(0)
    expect(loadZoneOffset(memStore({ [ZONE_KEY]: "-45" }))).toBe(0)
  })

  it("a blocked store falls back instead of throwing", () => {
    expect(loadZoneOffset(throwing)).toBe(0)
    expect(() => saveZoneOffset(-60, throwing)).not.toThrow()
  })

  it("survives having no storage at all, as a server render has none", () => {
    expect(loadZoneOffset(null)).toBe(0)
    expect(() => saveZoneOffset(-60, null)).not.toThrow()
  })
})
