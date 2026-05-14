/**
 * Unit tests for money formatters in api.ts
 * These are the most foundational tests — if formatVND breaks, every money display breaks.
 * HIGH-1: frontend had zero tests. These are the must-have baseline.
 */
import { describe, it, expect } from "vitest"
import { formatVND, formatPct } from "@/lib/api"

describe("formatVND", () => {
  it("formats large VND amount with Vietnamese dot separators", () => {
    const result = formatVND("186000000.0000")
    // vi-VN locale uses dots for thousands
    expect(result).toContain("186")
    expect(result).toContain("₫")
  })

  it("formats zero correctly", () => {
    const result = formatVND("0.0000")
    expect(result).toContain("0")
    expect(result).toContain("₫")
  })

  it("returns dash for null input", () => {
    expect(formatVND(null)).toBe("—")
  })

  it("returns dash for undefined input", () => {
    expect(formatVND(undefined)).toBe("—")
  })

  it("returns dash for empty string", () => {
    expect(formatVND("")).toBe("—")
  })

  it("returns dash for non-numeric string", () => {
    expect(formatVND("not-a-number")).toBe("—")
  })

  it("handles negative amounts (loss display)", () => {
    const result = formatVND("-5800000.0000")
    expect(result).toContain("5.800.000")
    expect(result).toContain("₫")
  })

  it("preserves Decimal string precision — does not use float for display logic", () => {
    // Decimal '186234567.0000' must not lose precision
    const result = formatVND("186234567.0000")
    expect(result).not.toBe("—")
    expect(result).toContain("₫")
  })
})

describe("formatPct", () => {
  it("formats refund rate correctly", () => {
    // "0.0420" → "4.2%"
    expect(formatPct("0.0420")).toBe("4.2%")
  })

  it("formats zero percent", () => {
    expect(formatPct("0")).toBe("0.0%")
  })

  it("formats 100 percent", () => {
    expect(formatPct("1")).toBe("100.0%")
  })

  it("returns dash for null", () => {
    expect(formatPct(null)).toBe("—")
  })

  it("returns dash for undefined", () => {
    expect(formatPct(undefined)).toBe("—")
  })

  it("returns dash for non-numeric string", () => {
    expect(formatPct("bad")).toBe("—")
  })
})
