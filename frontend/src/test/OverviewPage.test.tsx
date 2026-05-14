/**
 * Overview page integration tests — HIGH-1 frontend test coverage.
 *
 * This is the most important integration test in the suite.
 * It directly guards against BUG-CRITICAL-2: if actionsData?.items is undefined
 * (because API returns {items, total, pending_count} but type said AIActionResponse[]),
 * then pendingActions is always [] and action cards never render — silently.
 *
 * Test structure mirrors the real data flow:
 *   API returns AIActionListResponse → useActions() → actionsData?.items?.filter()
 *   → ActionCards rendered on overview page
 */
import { describe, it, expect } from "vitest"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { server, mockActionListResponse, mockInsightResponse } from "./msw-server"
import { renderWithProviders } from "./test-utils"

import OverviewPage from "@/app/(dashboard)/overview/page"

const API_BASE = "http://localhost:8000"

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("OverviewPage", () => {
  it("BUG-CRITICAL-2 REGRESSION: renders pending action cards from AIActionListResponse", async () => {
    // Backend returns {items: [...], total: 1, pending_count: 1}
    // If type was wrong (AIActionResponse[]), actionsData?.items would be undefined
    // and no ActionCards would render. This test catches that regression.
    renderWithProviders(<OverviewPage />)

    await waitFor(() => {
      expect(screen.getByText("Giảm voucher SKU Serum A")).toBeDefined()
    })

    // Action card content visible
    expect(screen.getByText(/Voucher 20% đang ăn hết margin/i)).toBeDefined()
    expect(screen.getByRole("button", { name: /đã làm/i })).toBeDefined()
    expect(screen.getByRole("button", { name: /bỏ qua/i })).toBeDefined()
  })

  it("renders P&L summary with insight data", async () => {
    renderWithProviders(<OverviewPage />)

    await waitFor(() => {
      // Should display GMV and net revenue from mockInsightResponse
      expect(screen.getByText(/186/)).toBeDefined()
    })
  })

  it("shows action count in section header", async () => {
    renderWithProviders(<OverviewPage />)

    await waitFor(() => {
      expect(screen.getByText(/Hành động hôm nay \(1\)/i)).toBeDefined()
    })
  })

  it("optimistically removes action card on dismiss", async () => {
    const user = userEvent.setup()
    renderWithProviders(<OverviewPage />)

    await waitFor(() => {
      expect(screen.getByText("Giảm voucher SKU Serum A")).toBeDefined()
    })

    const dismissBtn = screen.getByRole("button", { name: /bỏ qua/i })
    await user.click(dismissBtn)

    // After optimistic update, card should be gone
    await waitFor(() => {
      expect(screen.queryByText("Giảm voucher SKU Serum A")).toBeNull()
    })
  })

  it("shows empty state with import link when no insight data", async () => {
    server.use(
      http.get(`${API_BASE}/v1/insights/latest`, () =>
        HttpResponse.json({ detail: "No insight found" }, { status: 404 })
      )
    )

    renderWithProviders(<OverviewPage />)

    await waitFor(() => {
      expect(screen.getByText(/Chưa có dữ liệu/i)).toBeDefined()
      expect(screen.getByText(/Import file từ TikTok Shop/i)).toBeDefined()
    })
  })

  it("does not render action section when no pending actions", async () => {
    server.use(
      http.get(`${API_BASE}/v1/actions`, () =>
        HttpResponse.json({ items: [], total: 0, pending_count: 0 })
      )
    )

    renderWithProviders(<OverviewPage />)

    await waitFor(() => {
      // Insight loaded (GMV visible)
      expect(screen.getByText(/186/)).toBeDefined()
    })

    // Action section header should NOT be visible when no actions
    expect(screen.queryByText(/Hành động hôm nay/i)).toBeNull()
  })

  it("shows at most 3 action cards even when more exist", async () => {
    const manyActions = Array.from({ length: 5 }, (_, i) => ({
      ...mockActionListResponse.items[0],
      id: `action-00${i + 1}`,
      title: `Action ${i + 1}`,
      status: "pending",
    }))

    server.use(
      http.get(`${API_BASE}/v1/actions`, () =>
        HttpResponse.json({ items: manyActions, total: 5, pending_count: 5 })
      )
    )

    renderWithProviders(<OverviewPage />)

    await waitFor(() => {
      expect(screen.getByText("Action 1")).toBeDefined()
    })

    // Should show max 3 cards (slice(0, 3))
    expect(screen.queryByText("Action 4")).toBeNull()
    expect(screen.queryByText("Action 5")).toBeNull()
  })

  it("shows period range from insight", async () => {
    renderWithProviders(<OverviewPage />)

    await waitFor(() => {
      expect(screen.getByText(/2026-05-01/)).toBeDefined()
      expect(screen.getByText(/2026-05-07/)).toBeDefined()
    })
  })
})
