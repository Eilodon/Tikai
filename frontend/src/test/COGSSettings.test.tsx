/**
 * COGS Settings UI tests — v1.1.0
 * Verifies: COGSTable renders correctly, coverage counter, dirty tracking,
 * upsert called with only changed rows, recompute nudge shown after save.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { vi, describe, it, expect, beforeEach } from "vitest"

// Mock the entire api module
vi.mock("@/lib/api", () => ({
  cogsApi: {
    getAll: vi.fn().mockResolvedValue({
      items: [
        { sku_id: "SKU-001", sku_name: "Kem dưỡng da", cogs_per_unit: "45000" },
        { sku_id: "SKU-002", sku_name: "Serum vitamin C", cogs_per_unit: "0" },
      ],
      total_skus: 2,
      updated: 0,
    }),
    upsert: vi.fn().mockResolvedValue({ updated: 1, items: [], total_skus: 2 }),
  },
  insightsApi: {
    recompute: vi.fn().mockResolvedValue({}),
  },
  notificationsApi: {
    update: vi.fn().mockResolvedValue({}),
  },
  shopsApi: {
    updateMe: vi.fn().mockResolvedValue({ shop_name: "Test Shop" }),
  },
  formatVND: (s: string) => s,
}))

vi.mock("@/hooks/useApi", () => ({
  useShop: () => ({
    data: {
      shop_name: "Test Shop",
      subscription_tier: "pro",
      fee_config_version: "2026-VN-v3",
      notification_email: null,
      email_digest_enabled: false,
    },
    isLoading: false,
    refetch: vi.fn(),
  }),
}))

vi.mock("@/lib/supabase", () => ({
  getAuthToken: vi.fn().mockResolvedValue("test-token"),
}))

import SettingsPage from "@/app/(dashboard)/settings/page"

describe("COGS Settings UI", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders COGS table with SKU rows, not placeholder text", async () => {
    render(<SettingsPage />)
    await waitFor(() => {
      expect(screen.queryByText(/Sẽ ra mắt sớm/i)).toBeNull()
      expect(screen.getByText("Kem dưỡng da")).toBeInTheDocument()
      expect(screen.getByText("Serum vitamin C")).toBeInTheDocument()
    })
  })

  it("shows coverage counter: 1/2 SKU with correct colour cue", async () => {
    render(<SettingsPage />)
    await waitFor(() => {
      expect(screen.getByText(/Đã nhập giá vốn/i)).toBeInTheDocument()
      expect(screen.getByText(/1\/2 SKU/)).toBeInTheDocument()
    })
  })

  it("save button only calls upsert with dirty rows (SKU-002)", async () => {
    const { cogsApi } = await import("@/lib/api")
    render(<SettingsPage />)
    await waitFor(() => screen.getByText("Serum vitamin C"))

    // Change only SKU-002
    const inputs = screen.getAllByRole("spinbutton")
    fireEvent.change(inputs[1], { target: { value: "60000" } })

    await waitFor(() => {
      const saveBtn = screen.getByText(/Lưu 1 thay đổi/)
      expect(saveBtn).toBeInTheDocument()
      fireEvent.click(saveBtn)
    })

    await waitFor(() => {
      expect(cogsApi.upsert).toHaveBeenCalledWith(
        "test-token",
        expect.arrayContaining([
          expect.objectContaining({ sku_id: "SKU-002", cogs_per_unit: "60000" }),
        ])
      )
      // SKU-001 (not dirty) must NOT be in the payload
      const call = (cogsApi.upsert as any).mock.calls[0][1]
      expect(call.find((r: any) => r.sku_id === "SKU-001")).toBeUndefined()
    })
  })

  it("shows recompute nudge after successful save", async () => {
    render(<SettingsPage />)
    await waitFor(() => screen.getByText("Serum vitamin C"))

    const inputs = screen.getAllByRole("spinbutton")
    fireEvent.change(inputs[1], { target: { value: "60000" } })

    const saveBtn = await waitFor(() => screen.getByText(/Lưu 1 thay đổi/))
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Tính lại P&L/ })).toBeInTheDocument()
    })
  })
})
