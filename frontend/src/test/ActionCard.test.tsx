/**
 * ActionCard interaction tests — HIGH-1 frontend test coverage.
 *
 * Tests the most critical user-facing interaction in the Behavioral Outcome Loop:
 * seller sees an action → marks it complete or dismisses it.
 * These guard against the BUG-CRITICAL-2 class of silent UI failures.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ActionCard } from "@/components/actions/ActionCard"
import type { AIActionResponse } from "@/lib/api"

// ── Fixture ───────────────────────────────────────────────────────────────────

const mockAction: AIActionResponse = {
  id: "action-001",
  shop_id: "shop-001",
  action_type: "reduce_voucher",
  rule_trigger: "voucher_high",
  title: "Giảm voucher SKU Serum A xuống 8%",
  why: "Voucher 20% đang ăn hết margin — net margin hiện tại -2.3%",
  do_today: "Vào TikTok Seller Center → Khuyến mãi → Giảm voucher SKU-001 từ 20% xuống 8%",
  expected_impact: "Margin tăng từ -2.3% lên ~6.1%, tiết kiệm khoảng 3.2M/tuần",
  confidence: "high",
  status: "pending",
  completed_at: null,
  is_confirmed_impact: false,
  confirmed_delta: null,
  created_at: "2026-05-17T00:00:00Z",
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ActionCard", () => {
  it("renders action title, why, and do_today", () => {
    render(
      <ActionCard
        action={mockAction}
        onComplete={vi.fn()}
        onDismiss={vi.fn()}
      />
    )

    expect(screen.getByText("Giảm voucher SKU Serum A xuống 8%")).toBeDefined()
    expect(screen.getByText(/Voucher 20% đang ăn hết margin/)).toBeDefined()
    expect(screen.getByText(/Vào TikTok Seller Center/)).toBeDefined()
  })

  it("calls onComplete when '✓ Đã làm' button is clicked", async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()

    render(
      <ActionCard
        action={mockAction}
        onComplete={onComplete}
        onDismiss={vi.fn()}
      />
    )

    const completeBtn = screen.getByRole("button", { name: /đã làm/i })
    await user.click(completeBtn)

    expect(onComplete).toHaveBeenCalledTimes(1)
  })

  it("calls onDismiss when 'Bỏ qua' button is clicked", async () => {
    const onDismiss = vi.fn()
    const user = userEvent.setup()

    render(
      <ActionCard
        action={mockAction}
        onComplete={vi.fn()}
        onDismiss={onDismiss}
      />
    )

    const dismissBtn = screen.getByRole("button", { name: /bỏ qua/i })
    await user.click(dismissBtn)

    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it("disables complete button and shows loading text when completing=true", () => {
    render(
      <ActionCard
        action={mockAction}
        onComplete={vi.fn()}
        onDismiss={vi.fn()}
        completing={true}
      />
    )

    const completeBtn = screen.getByRole("button", { name: /đang lưu/i })
    expect(completeBtn).toHaveProperty("disabled", true)
  })

  it("does not call onComplete when button is disabled (completing=true)", async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()

    render(
      <ActionCard
        action={mockAction}
        onComplete={onComplete}
        onDismiss={vi.fn()}
        completing={true}
      />
    )

    const completeBtn = screen.getByRole("button", { name: /đang lưu/i })
    await user.click(completeBtn)

    // disabled button should not fire handler
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("renders expected_impact text when present", () => {
    render(
      <ActionCard
        action={mockAction}
        onComplete={vi.fn()}
        onDismiss={vi.fn()}
      />
    )
    expect(screen.getByText(/Kỳ vọng:/)).toBeDefined()
    expect(screen.getByText(/tiết kiệm khoảng 3.2M/)).toBeDefined()
  })

  it("does not crash when expected_impact is empty string", () => {
    const noImpact = { ...mockAction, expected_impact: "" }
    expect(() =>
      render(<ActionCard action={noImpact} onComplete={vi.fn()} onDismiss={vi.fn()} />)
    ).not.toThrow()
  })

  it("renders high confidence badge correctly", () => {
    render(
      <ActionCard
        action={{ ...mockAction, confidence: "high" }}
        onComplete={vi.fn()}
        onDismiss={vi.fn()}
      />
    )
    // ConfidenceBadge renders confidence level — check it's present in DOM
    expect(screen.getByText("Chắc chắn")).toBeDefined()
  })
})
