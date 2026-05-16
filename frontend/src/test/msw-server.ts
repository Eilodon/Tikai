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
  shop_id: "shop-001",
  period_start: "2026-05-01",
  period_end: "2026-05-07",
  gmv_total: "186000000.0000",
  net_revenue: "122500000.0000",
  total_orders: 312,
  total_refunds: 13,
  refund_rate: "0.0420",
  cash_in_14d: "89000000.0000",
  cash_in_30d: "142000000.0000",
  cash_pending_total: "53000000.0000",
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
  top_skus: [
    {
      sku_id: "SKU-001",
      sku_name: "Serum Vitamin C 30ml",
      gmv: "92000000.0000",
      net_revenue: "61000000.0000",
      order_count: 156,
      total_quantity: 180,
      refund_rate: "0.0380",
      margin_pct: "0.1200",
      margin: "7320000.0000",
      gmv_rank: 1,
      affiliate_commission: "9200000.0000",
      voucher_cost: "4600000.0000",
      health_status: "healthy",
      health_reasons: [],
    },
  ],
  top_creators: [
    {
      creator_id: "creator-001",
      creator_name: "Creator A",
      attributed_gmv: "55000000.0000",
      attributed_net_revenue: "36000000.0000",
      total_commission: "5500000.0000",
      order_count: 88,
      revenue_efficiency: "6.55",
      performance_label: "good",
      suggested_max_commission_rate: "0.08",
      commission_on_refunded_orders: "550000.0000",
    },
  ],
  action_triggers: [],
  rule_engine_version: "0.1.0",
  fee_config_version: "v3",
  cogs_coverage_pct: "0.8500",
  is_net_revenue_mode: false,
  days_in_period: 7,
  is_partial_period: false,
  is_first_import: false,
  created_at: "2026-05-08T01:00:00Z",
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
