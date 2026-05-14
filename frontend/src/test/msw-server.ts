/**
 * MSW (Mock Service Worker) server for Vitest.
 * Intercepts fetch calls made by components under test.
 * Handlers return minimal valid shapes matching backend Pydantic schemas.
 */
import { setupServer } from "msw/node"
import { http, HttpResponse } from "msw"

const API_BASE = "http://localhost:8000"

// ── Fixtures ──────────────────────────────────────────────────────────────────

export const mockActionListResponse = {
  items: [
    {
      id: "action-001",
      action_type: "reduce_voucher",
      title: "Giảm voucher SKU Serum A",
      why: "Voucher 20% đang ăn hết margin",
      do_today: "Vào TikTok Seller Center giảm voucher xuống 8%",
      expected_impact: "Margin tăng từ -2% lên 6%",
      confidence: "high",
      status: "pending",
      completed_at: null,
    },
  ],
  total: 1,
  pending_count: 1,
}

export const mockInsightResponse = {
  id: "snapshot-001",
  period_start: "2026-05-01",
  period_end: "2026-05-07",
  gmv_total: "186000000.0000",
  net_revenue: "122500000.0000",
  total_orders: 312,
  refund_rate: "0.0420",
  cash_in_14d: "89000000.0000",
  top_leaks: [
    {
      type: "sku",
      id: "SKU-001",
      name: "Serum Vitamin C 30ml",
      estimated_loss: "5800000.0000",
      reason: "voucher_high",
      confidence: "high",
      can_act_now: true,
    },
  ],
  is_net_revenue_mode: false,
  cogs_coverage_pct: "0.8500",
  rule_engine_version: "0.1.0",
}

// ── Default handlers ──────────────────────────────────────────────────────────

export const handlers = [
  http.get(`${API_BASE}/v1/actions`, () =>
    HttpResponse.json(mockActionListResponse)
  ),
  http.get(`${API_BASE}/v1/insights/latest`, () =>
    HttpResponse.json(mockInsightResponse)
  ),
  http.patch(`${API_BASE}/v1/actions/:id/complete`, ({ params }) =>
    HttpResponse.json({ ...mockActionListResponse.items[0], id: params.id, status: "done" })
  ),
  http.patch(`${API_BASE}/v1/actions/:id/dismiss`, ({ params }) =>
    HttpResponse.json({ ...mockActionListResponse.items[0], id: params.id, status: "dismissed" })
  ),
]

export const server = setupServer(...handlers)
