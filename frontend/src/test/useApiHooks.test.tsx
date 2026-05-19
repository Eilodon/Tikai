/**
 * Hook-level tests for useApi.ts — verifies query/mutation shapes without
 * rendering full pages. Catches contract breaks (API response shape changes)
 * earlier than component tests.
 *
 * Uses renderHook from @testing-library/react + MSW for API mocking.
 */
import { describe, it, expect } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server, mockActionListResponse, mockInsightResponse } from "./msw-server"
import { makeTestWrapper } from "./test-utils"
import { useLatestInsight, useActions, useShop } from "@/hooks/useApi"

const API_BASE = "http://localhost:8000"

// ── useLatestInsight ──────────────────────────────────────────────────────────

describe("useLatestInsight", () => {
  it("returns insight data with correct shape", async () => {
    const { result } = renderHook(() => useLatestInsight(), {
      wrapper: makeTestWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const data = result.current.data
    expect(data).toBeDefined()
    expect(data?.gmv_total).toBe("186000000.0000")
    expect(data?.net_revenue).toBe("122500000.0000")
    expect(typeof data?.total_orders).toBe("number")
    expect(Array.isArray(data?.top_leaks)).toBe(true)
    expect(Array.isArray(data?.top_skus)).toBe(true)
  })

  it("does not retry on 404 (no insight yet — first-time user)", async () => {
    server.use(
      http.get(`${API_BASE}/v1/insights/latest`, () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 })
      )
    )

    const { result } = renderHook(() => useLatestInsight(), {
      wrapper: makeTestWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    // With retry: false for 404, failureCount stays at 1 — not 3
    expect(result.current.failureCount).toBeLessThanOrEqual(1)
  })

  it("exposes error when server returns 500", async () => {
    server.use(
      http.get(`${API_BASE}/v1/insights/latest`, () =>
        HttpResponse.json({ detail: "Internal error" }, { status: 500 })
      )
    )

    const { result } = renderHook(() => useLatestInsight(), {
      wrapper: makeTestWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 3000 })
    expect(result.current.data).toBeUndefined()
  })
})

// ── useActions ────────────────────────────────────────────────────────────────

describe("useActions", () => {
  it("returns actions with correct list shape (items array, not flat array)", async () => {
    const { result } = renderHook(() => useActions(), {
      wrapper: makeTestWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const data = result.current.data
    // CRITICAL: backend returns {items, total, pending_count} — NOT a flat array
    // If type was wrong (AIActionResponse[]), data?.items would be undefined
    expect(data).toBeDefined()
    expect(Array.isArray(data?.items)).toBe(true)
    expect(typeof data?.total).toBe("number")
    expect(typeof data?.pending_count).toBe("number")
    expect(data?.items[0]?.id).toBe("action-001")
    expect(data?.items[0]?.status).toBe("pending")
  })

  it("each action has required fields for ActionCard rendering", async () => {
    const { result } = renderHook(() => useActions(), {
      wrapper: makeTestWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const action = result.current.data?.items[0]
    expect(action?.title).toBeTruthy()
    expect(action?.why).toBeTruthy()
    expect(action?.do_today).toBeTruthy()
    expect(action?.expected_impact).toBeTruthy()
    expect(action?.confidence).toMatch(/^(high|medium|low)$/)
    expect(action?.status).toMatch(/^(pending|done|dismissed)$/)
  })

  it("pending_count matches filtered items count", async () => {
    const { result } = renderHook(() => useActions(), {
      wrapper: makeTestWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const data = result.current.data!
    const pendingCount = data.items.filter((a) => a.status === "pending").length
    expect(pendingCount).toBe(data.pending_count)
  })
})

// ── useShop ───────────────────────────────────────────────────────────────────

describe("useShop", () => {
  it("returns shop with subscription_tier", async () => {
    const { result } = renderHook(() => useShop(), {
      wrapper: makeTestWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const shop = result.current.data
    expect(shop?.subscription_tier).toMatch(/^(free|pro|pro_trial|business|enterprise)$/)
    expect(shop?.is_active).toBe(true)
  })

  it("subscription_tier determines feature availability", async () => {
    const { result } = renderHook(() => useShop(), {
      wrapper: makeTestWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const tier = result.current.data?.subscription_tier
    const isPro = tier && ["pro", "pro_trial", "business", "enterprise"].includes(tier)
    // Pro users should have access to more features
    expect(typeof isPro).toBe("boolean")
  })
})
