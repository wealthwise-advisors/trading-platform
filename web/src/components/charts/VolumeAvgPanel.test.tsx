// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { VolumeAvgPanel } from "./VolumeAvgPanel"

afterEach(cleanup)

describe("VolumeAvgPanel", () => {
  it("shows the length and reports a change", () => {
    const onLength = vi.fn()
    render(<VolumeAvgPanel length={20} onLength={onLength} onClose={() => {}} />)
    const input = screen.getByLabelText("VolumeAvg length") as HTMLInputElement
    expect(input.value).toBe("20")
    fireEvent.change(input, { target: { value: "50" } })
    expect(onLength).toHaveBeenCalledWith(50)
  })

  it("closes on Escape", () => {
    const onClose = vi.fn()
    render(<VolumeAvgPanel length={20} onLength={() => {}} onClose={onClose} />)
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" })
    expect(onClose).toHaveBeenCalled()
  })
})
